from flask import Blueprint, render_template, request, flash, redirect,url_for, jsonify
from .models import User, Ingredients, Recipe,Inventory
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from flask_login import login_user, login_required, logout_user, current_user
from sqlalchemy import func

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET','POST'])
def login():
    nameCheck = User.query.filter(func.lower(User.user_name) == 
                                                 func.lower('admin')).first()
    if nameCheck:
        adminAcct = True
    else:
        adminAcct = False
        

    if request.method == 'POST':
        if request.form['action'] == 'login':
            user_name = request.form.get('user_name')
            password = request.form.get('password')

            user = User.query.filter_by(user_name=user_name).first()
            if user:
                if check_password_hash(user.password, password):
                    flash('Logged in successfully!',category='success')
                    login_user(user, remember=True)
                    return redirect(url_for('views.home'))
                else:
                    flash('Incorrect password',category='error')

        #not needed due to create_admin function in create.py            
        #if request.form['action'] == 'addAcct':
            #admin = User(user_name='admin',password=generate_password_hash('admin777',method='scrypt'),position='admin',
                #first_name='admin',last_name='admin')
            #db.session.add(admin)
            #db.session.commit()
            #return redirect(url_for('auth.login'))

    return render_template("login.html", user=current_user, adminAcct=adminAcct)



@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/createaccount', methods=['GET','POST'])
def createaccount():
    allowed_positions = ['admin', 'Manager']

    if current_user.position not in allowed_positions:
        flash('You are not authorized to access this page.', category='error')
        return redirect(url_for('views.home'))

    
    allUsers = User.query.filter(User.id != 1).order_by(User.last_name, User.first_name).all()

    if request.method == 'POST':
        if request.form['action'] == 'addUser':
            user_name = request.form.get('userName')
            first_name = request.form.get('firstName')
            last_name = request.form.get('lastName')
            password1 = request.form.get('password1')
            password2 = request.form.get('password2')
            position = request.form.get('position')

            user = User.query.filter_by(user_name=user_name).first()

            if user:
                flash('Username already exists',category='error')
            elif len(user_name) < 4:
                flash('Username must be at least 4 characters', category='error')
            elif len(first_name) < 2:
                flash('First name must be at least 2 characters', category='error')
            elif len(last_name) < 2:
                flash('Last name must be at least 2 characters', category='error')
            elif password1 != password2:
                flash('Password don\'t match', category='error')
            elif len(password1) < 6:
                flash('Password must be at least 6 characters', category='error')
            elif position == '---':
                flash('Position cannot be empty', category='error')
            else:
                new_user = User(user_name=user_name, first_name=first_name, last_name=last_name, 
                            password=generate_password_hash(password1,method='scrypt'),
                            position=position)
                db.session.add(new_user)
                db.session.commit()
                #login_user(user,remember=True)
                flash('Account created!', category='success')
                return redirect(url_for('auth.createaccount'))
        if request.form['action'] == 'checkUser':
            selectedUserId = request.form['userListSelect']
            selectedUser = User.query.get(selectedUserId)
            return render_template("signup.html",user=current_user,allUsers=allUsers,
                                   selectedUser=selectedUser)
        if request.form['action'] == 'editPosition':
            editPositionUser = request.form['positionUser']
            newPosition = request.form['editPosition']
            editPositionQuery = User.query.get(editPositionUser)

            if editPositionQuery:
                editPositionQuery.position = newPosition
                db.session.commit()
                flash('Edit Completed!',category='success')
                return render_template("signup.html",user=current_user,allUsers=allUsers,
                                   selectedUser=editPositionQuery)
        if request.form['action'] == 'editPassword':
            editPassUser = request.form['passUser']
            newPassword1 = request.form['newPassword']
            newPassword2 = request.form['newPassword2']
            editPasswordQuery = User.query.get(editPassUser)

            if newPassword1 != newPassword2:
                flash('Password don\'t match', category='error')
            elif len(newPassword1) < 6:
                flash('Password must be at least 6 characters', category='error')
            else:
                editPasswordQuery.password = generate_password_hash(newPassword1,method='scrypt')
                db.session.commit()
                flash('Edit Completed!',category='success')
                return render_template("signup.html",user=current_user,allUsers=allUsers,
                                   selectedUser=editPasswordQuery)
        if request.form['action'] == 'deleteUser':
            deleteUser = request.form['deleteUser']

            deleteUserQuery = User.query.get(deleteUser)
            if deleteUserQuery:
                db.session.delete(deleteUserQuery)
                db.session.commit()
                return redirect(url_for('auth.createaccount'))
        
        
    return render_template("signup.html",user=current_user,allUsers=allUsers)
