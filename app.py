from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
from datetime import datetime

######################
######   init   ######
######################
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"
app.config['SECRET_KEY'] = 'this_is_so_random_sagi'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

######################

######################
######  models  ######
######################
class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)
    friends = db.relationship('User', secondary='friendship',
                            primaryjoin=(Friendship.user_id == id),
                            secondaryjoin=(Friendship.friend_id == id),
                            backref=db.backref('friendship', lazy='dynamic'), lazy='dynamic')

    def __init__(self,username,password):
        self.username = username
        self.password = password

    def is_friend(self, user):
        return self.friends.filter_by(id=user.id).first() is not None
    
    def is_friend_by_username(self, username):
        friend = User.query.filter_by(username=username).first()
        return self.is_friend(friend) if friend else False

    def add_friend(self, user):
            if not self.is_friend(user):
                self.friends.append(user)
                user.friends.append(self)
                db.session.commit()

    def remove_friend(self, user):
        if self.is_friend(user):
            self.friends.remove(user)
            user.friends.remove(self)
            db.session.commit()

def current_time():
    return datetime.utcnow().strftime('%d-%m-%Y, %H:%M')

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.String(5), nullable=False, default=current_time)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

######################
    
######################
######  forms   ######
######################
class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min = 4, max = 20)], render_kw={"placeholder" : "Username"})
    password = StringField(validators=[InputRequired(), Length(
        min = 4, max = 20)], render_kw={"placeholder" : "Password"})
    submit = SubmitField("Register")

    def validate_username(self, username):
        existing_user_name = User.query.filter_by(username = username.data).first()
        if existing_user_name:
            raise ValidationError("Username already exists! Please choose a different one.")

class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min = 4, max = 20)], render_kw={"placeholder" : "Username"})
    password = StringField(validators=[InputRequired(), Length(
        min = 4, max = 20)], render_kw={"placeholder" : "Password"})
    submit = SubmitField("Login")
######################

######################
######  routes  ######
######################
@app.route('/')
def home():
    return render_template("home.html")

@app.route('/home_page')
def home_page():
    # Retrieve posts from the current user and their friends
    c_user = User.query.filter_by(username=current_user.username).first() 
    friends = c_user.friends 
    c_user_posts = Post.query.filter_by(user_id=current_user.id).all()
    
    posts = []
    for post in c_user_posts:
        posts.append({
                'id': post.id,
                'content': post.content,
                'username': c_user.username,
                'created_at': post.created_at 
            })

    for friend in friends:
        friend_posts = Post.query.filter_by(user_id=friend.id).all()
        for post in friend_posts:
            posts.append({
                'id': post.id,
                'content': post.content,
                'username': friend.username,
                'created_at': post.created_at 
            })
        
    sorted_posts = sorted(posts, key=lambda x: x["created_at"], reverse=True)
    return render_template('home_page.html', posts=sorted_posts, username=current_user.username)

@app.route('/add_friend/<username>', methods=['POST'])
@login_required
def add_friend(username):
    user = User.query.filter_by(username=username).first()
    current_user.add_friend(user)
    return redirect(url_for('users_list'))

@app.route('/remove_friend/<username>', methods=['POST'])
@login_required
def remove_friend(username):
    user = User.query.filter_by(username=username).first()
    current_user.remove_friend(user)
    return redirect(url_for('users_list'))

@app.route('/profile/<username>', methods = ['GET', 'POST'])
@login_required
def profile(username):
    
    user = User.query.filter_by(username=username).first_or_404()
    user_posts = Post.query.filter_by(user_id=user.id).all()
    posts = []
    for post in user_posts:
        posts.append({
                'id': post.id,
                'content': post.content,
                'username': user.username,
                'created_at': post.created_at 
            })
        
    sorted_posts = sorted(posts, key=lambda x: x["created_at"], reverse=True)
    return render_template('user_profile.html', current_user=current_user, username=user.username, user_posts=sorted_posts)

#turned this into explore page
@app.route('/users_list')
@login_required
def users_list():
    user = User.query.filter_by(username=current_user.username).first()
    subquery = db.session.query(Friendship.friend_id).filter_by(user_id=user.id).subquery()
    
    posts = Post.query.filter(Post.user_id.notin_(subquery), Post.user_id != user.id).order_by(Post.created_at.desc()).all()
    for post in posts:
        user_id = post.user_id
        username = get_username_from_user_id(user_id)
        post.username = username

    return render_template('users_list.html', posts=posts, c_user=user)

@app.route('/friends_list', methods = ['GET', 'POST'])
@login_required
def friends_list():
    if request.method == 'POST':
        username = request.form.get('username')
        user = User.query.filter_by(username=username).first()
        current_user.remove_friend(user)
        friends = current_user.friends.all()
    else:        
        user = User.query.filter_by(username=current_user.username).first_or_404()
        friends = user.friends.all()  # Retrieve the user's friends from the database

    return render_template('friends_list.html', user=current_user, friends=friends)

@app.route('/add_post', methods=['POST'])
@login_required
def add_post():
    post_content = request.form.get('post_content')
    if post_content:
        new_post = Post(content=post_content, user_id=current_user.id)
        db.session.add(new_post)
        db.session.commit()

    # return redirect(url_for('profile', username=current_user.username))
    return redirect(url_for('home_page'))

@app.route('/login', methods = ['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
       user = User.query.filter_by(username=form.username.data).first()
       if user:
           if bcrypt.check_password_hash(user.password, form.password.data):
               login_user(user)
            #    return redirect(url_for('profile',username = form.username.data))
               return redirect(url_for('home_page'))
           else:
               return render_template('error.html', error="wrong password!")
       else:
        return render_template('error.html', error="username not found!")
       
    return render_template("login.html", form=form)

@app.route('/logout', methods = ['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/register', methods = ['GET', 'POST'])
def register():
    form = RegisterForm()
    if request.method =="POST":
        if form.validate_on_submit():
            hashed_password = bcrypt.generate_password_hash(form.password.data)
            new_user = User(username = form.username.data, password = hashed_password)
            db.session.add(new_user)
            db.session.commit()

            return redirect(url_for('login'))
        else:
            return render_template('error.html', error="registration went wrong. try different username/password!")
    else:
        return render_template("register.html",form=form)

def get_username_from_user_id(user_id):
    user = User.query.filter_by(id=user_id).first()
    if user:
        return user.username
    else:
        return None
######################

######################
######   main   ######
######################
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        app.run(debug=True)