from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import random
import traceback 


app = Flask(__name__)
CORS(app) 
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:dhruv%402808@localhost:3306/schedule'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ========================== MODELS =============================

class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Teacher(db.Model):
    __tablename__ = 'teachers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    available_slots = db.Column(db.Text, nullable=False)  # e.g., "Mon-1,Mon-2"

class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'theory' or 'practical'
    lectures_per_week = db.Column(db.Integer, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    teacher = db.relationship('Teacher')

class ClassSubject(db.Model):
    __tablename__ = 'class_subjects'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    class_ = db.relationship('Class')
    subject = db.relationship('Subject')

class Timetable(db.Model):
    __tablename__ = 'timetable'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    day = db.Column(db.String(10))
    slot = db.Column(db.String(10))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    type = db.Column(db.String(20))  # theory or practical
    class_ = db.relationship('Class')
    subject = db.relationship('Subject')
    teacher = db.relationship('Teacher')

# ========================== GLOBALS =============================
DAYS = []
SLOTS = []
BREAK_SLOTS = []

# ========================== SCHEDULING LOGIC =============================

def generate_schedule():
    db.session.query(Timetable).delete()

    used_slots_by_teacher = {}

    for class_ in Class.query.all():
        class_subjects = ClassSubject.query.filter_by(class_id=class_.id).all()
        subject_slots_remaining = {cs.subject_id: cs.subject.lectures_per_week for cs in class_subjects}

        for day in DAYS:
            slot_idx = 0
            while slot_idx < len(SLOTS):
                slot = SLOTS[slot_idx]
                if slot in BREAK_SLOTS:
                    slot_idx += 1
                    continue

                random.shuffle(class_subjects)

                for cs in class_subjects:
                    subject = cs.subject
                    teacher = subject.teacher
                    key = f"{day}-{slot}"

                    if subject_slots_remaining[subject.id] <= 0:
                        continue
                    if key not in teacher.available_slots:
                        continue
                    if key in used_slots_by_teacher and teacher.id in used_slots_by_teacher[key]:
                        continue

                    # Practical = 2 consecutive slots
                    if subject.type == 'practical':
                        if slot_idx + 1 >= len(SLOTS) or SLOTS[slot_idx + 1] in BREAK_SLOTS:
                            continue
                        next_slot = SLOTS[slot_idx + 1]
                        key_next = f"{day}-{next_slot}"
                        if key_next not in teacher.available_slots:
                            continue
                        if key_next in used_slots_by_teacher and teacher.id in used_slots_by_teacher[key_next]:
                            continue

                        db.session.add(Timetable(class_id=class_.id, day=day, slot=slot,
                                                 subject_id=subject.id, teacher_id=teacher.id, type='practical'))
                        db.session.add(Timetable(class_id=class_.id, day=day, slot=next_slot,
                                                 subject_id=subject.id, teacher_id=teacher.id, type='practical'))
                        used_slots_by_teacher.setdefault(key, []).append(teacher.id)
                        used_slots_by_teacher.setdefault(key_next, []).append(teacher.id)
                        subject_slots_remaining[subject.id] -= 1
                        slot_idx += 2
                        break

                    else:  # theory
                        db.session.add(Timetable(class_id=class_.id, day=day, slot=slot,
                                                 subject_id=subject.id, teacher_id=teacher.id, type='theory'))
                        used_slots_by_teacher.setdefault(key, []).append(teacher.id)
                        subject_slots_remaining[subject.id] -= 1
                        slot_idx += 1
                        break
                else:
                    slot_idx += 1

    db.session.commit()

    result = Timetable.query.all()
    return [{
        "class": r.class_.name,
        "day": r.day,
        "slot": r.slot,
        "subject": r.subject.name,
        "teacher": r.teacher.name,
        "type": r.type
    } for r in result]

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/add_class', methods=['POST'])
def add_class():
    data = request.json
    new_class = Class(name=data['name'])
    db.session.add(new_class)
    db.session.commit()
    return jsonify({'message': 'Class added'}), 201

@app.route('/add_teacher', methods=['POST'])
def add_teacher():
    data = request.json
    new_teacher = Teacher(name=data['name'], available_slots=data['available_slots'])
    db.session.add(new_teacher)
    db.session.commit()
    return jsonify({'message': 'Teacher added'}), 201

@app.route('/add_subject', methods=['POST'])
def add_subject():
    data = request.json
    new_subject = Subject(
        name=data['name'],
        type=data['type'],
        lectures_per_week=data['lectures_per_week'],
        teacher_id=data['teacher_id']
    )
    db.session.add(new_subject)
    db.session.commit()
    return jsonify({'message': 'Subject added'}), 201

@app.route('/add_class_subject', methods=['POST'])
def add_class_subject():
    data = request.json
    link = ClassSubject(class_id=data['class_id'], subject_id=data['subject_id'])
    db.session.add(link)
    db.session.commit()
    return jsonify({'message': 'Class-Subject link added'}), 201

@app.route('/timetable', methods=['GET'])
def get_timetable():
    timetable = Timetable.query.all()
    return jsonify([{
        "class": r.class_.name,
        "day": r.day,
        "slot": r.slot,
        "subject": r.subject.name,
        "teacher": r.teacher.name,
        "type": r.type
    } for r in timetable])


# ========================== API =============================

@app.route('/generate_schedule', methods=['POST'])
def generate():
    try:
        data = request.json

        # Step 1: Clear old entries
        db.session.query(Timetable).delete()
        db.session.query(ClassSubject).delete()
        db.session.query(Subject).delete()
        db.session.query(Teacher).delete()
        db.session.query(Class).delete()
        db.session.commit()

        # Step 2: Update globals
        global DAYS, SLOTS, BREAK_SLOTS
        DAYS = data['days']
        SLOTS = data['slots']
        BREAK_SLOTS = data['breaks']

        # Step 3: Insert new teachers
        teacher_map = {}
        for t in data['teachers']:
            teacher = Teacher(name=t['name'], available_slots=','.join(t['available']))
            db.session.add(teacher)
            db.session.flush()  # to get teacher.id
            teacher_map[t['name']] = teacher.id

        # Step 4: Insert new subjects
        subject_map = {}
        for s in data['subjects']:
            subject = Subject(
                name=s['name'],
                type=s['type'],
                lectures_per_week=s['lectures'],
                teacher_id=teacher_map[s['teacher']]
            )
            db.session.add(subject)
            db.session.flush()
            subject_map[s['name']] = subject.id

        # Step 5: Insert classes and assign subjects
        for cls in data['classes']:
            class_obj = Class(name=cls['name'])
            db.session.add(class_obj)
            db.session.flush()
            for subject_name in cls['subjects']:
                db.session.add(ClassSubject(class_id=class_obj.id, subject_id=subject_map[subject_name]))

        db.session.commit()

        # Step 6: Generate schedule
        schedule = generate_schedule()
        return jsonify({"message": "Schedule generated successfully!", "data": schedule}), 200

    except Exception as e:
        db.session.rollback()
        print("===== ERROR in /generate_schedule =====")
        traceback.print_exc() 
        return jsonify({"error": str(e)}), 500
    
    

# ========================== RUN =============================

if __name__ == '__main__':
    app.run(debug=True)
