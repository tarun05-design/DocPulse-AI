import re

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from ..extensions import db
from ..models import User, AuditLog

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 6


@auth_bp.post("/register")
def register():
    data = request.get_json(force=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"error": "name, email and password are required"}), 400

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Please provide a valid email address"}), 400

    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"Password must be at least {MIN_PASSWORD_LENGTH} characters"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with that email already exists"}), 409

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    db.session.add(AuditLog(user_id=user.id, action="register", details=f"user {email} registered"))
    db.session.commit()

    token = create_access_token(identity=user.id)
    return jsonify({"token": token, "user": user.to_dict()}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(force=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(identity=user.id)
    db.session.add(AuditLog(user_id=user.id, action="login", details="successful login"))
    db.session.commit()

    return jsonify({"token": token, "user": user.to_dict()})


@auth_bp.get("/me")
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict())


@auth_bp.put("/profile")
@jwt_required()
def update_profile():
    """Update the current user's name."""
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(force=True) or {}
    name = data.get("name", "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400

    user.name = name
    db.session.add(AuditLog(user_id=user.id, action="profile_update", details=f"name changed to {name}"))
    db.session.commit()

    return jsonify(user.to_dict())


@auth_bp.put("/password")
@jwt_required()
def change_password():
    """Change the current user's password."""
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(force=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"error": "current_password and new_password are required"}), 400

    if not user.check_password(current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    if len(new_password) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"New password must be at least {MIN_PASSWORD_LENGTH} characters"}), 400

    user.set_password(new_password)
    db.session.add(AuditLog(user_id=user.id, action="password_change", details="password changed"))
    db.session.commit()

    return jsonify({"message": "Password changed successfully"})

