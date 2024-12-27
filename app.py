import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets
from flask_cors import CORS
from utils import send_email  # Assurez-vous que cette fonction est définie correctement

# Initialisation de Flask et CORS
app = Flask(__name__)
CORS(app)

# Activer CSRF

# Configuration de la base de données et JWT
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:123456@localhost/ocr_auth_db'  # Remplacez par votre propre URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'votre_secret_key'  # Remplacez par une clé secrète de votre choix
app.config['UPLOAD_FOLDER'] = 'uploads'

# Initialisation de la base de données et JWT
db = SQLAlchemy(app)
jwt = JWTManager(app)

# Modèle de la table User
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)  # Augmenté à 256
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(64), nullable=True)
    token_expiration = db.Column(db.DateTime, nullable=True)

# Route d'inscription
import re

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not is_valid_email(email):
        return jsonify({"error": "Adresse email invalide!"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "L'email existe déjà!"}), 400
    
    if len(password) < 6:
        return jsonify({"error": "Mot de passe trop court!"}), 400
    
    password_hash = generate_password_hash(password)
    token = secrets.token_urlsafe(24)
    token_expiration = datetime.utcnow() + timedelta(hours=1)
    
    new_user = User(email=email, password_hash=password_hash, verification_token=token, token_expiration=token_expiration)
    db.session.add(new_user)
    db.session.commit()

    verification_url = f"http://127.0.0.1:5001/verify_email/{token}"
    send_email(email, "Vérification de compte", f"Cliquez sur ce lien pour vérifier votre compte : {verification_url}")
    
    return jsonify({"message": "Utilisateur enregistré. Veuillez vérifier votre email."}), 201

# Route de vérification d'email
@app.route('/verify_email/<token>', methods=['GET'])
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if user and datetime.utcnow() < user.token_expiration:
        user.is_verified = True
        user.verification_token = None  # Effacer le token après la vérification
        db.session.commit()
        return jsonify({"message": "Votre compte a été vérifié avec succès!"})
    
    return jsonify({"error": "Token invalide ou expiré!"}), 400

# Route de connexion (Login)
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        if not user.is_verified:
            return jsonify({"error": "Votre compte n'est pas vérifié!"}), 400
        
        # Créer un token JWT
        access_token = create_access_token(identity=email)
        return jsonify(access_token=access_token)
    
    return jsonify({"error": "Identifiants incorrects!"}), 401

# Route protégée (exemple)
@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user)

# Créer toutes les tables dans la base de données MySQL
with app.app_context():
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    
    if 'user' not in tables:
        db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)