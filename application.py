# Uses request.args.get

from flask import Flask, render_template, redirect, request, session
from cs50 import SQL
from datetime import datetime, timezone
from flask_session import Session
from helpers import apology, login_required, lookup, usd, is_int
from werkzeug.security import check_password_hash, generate_password_hash

application = Flask(__name__)

# Ensure templates are auto-reloaded
application.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
# app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
application.config["SESSION_PERMANENT"] = False
application.config["SESSION_TYPE"] = "filesystem"
Session(application)

db = SQL("sqlite:///social.db")


def time_ago(diff):
    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds // 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"
    elif seconds < 2419200:  # roughly 4 weeks
        weeks = int(seconds // 604800)
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    else:
        # If it's beyond weeks, you can decide whether to return months/years
        months = int(seconds // 2419200)
        return f"{months} month{'s' if months > 1 else ''} ago"


@application.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "GET":
        # Fetch all posts with associated comments (if any), regardless of the user who posted them
        posts_with_comments = db.execute(
            """
            SELECT 
                Post.ID as postID, 
                Post.imageUrl as imageUrl, 
                Post.createdDate as postDate, 
                User.ID as userID, 
                User.handler, 
                Song.songName, 
                Song.songUrl, 
                Comment.userID as commentUserID, 
                Comment.content as commentContent, 
                Comment.createdDate as commentCreatedDate,
                U.name as commentUserName,
                U.imageUrl as commentAvatar
            FROM Post 
            JOIN Song ON Post.songID = Song.ID 
            JOIN User ON Post.userID = User.ID
            LEFT JOIN Comment ON Post.ID = Comment.postID
            LEFT JOIN User U ON Comment.userID = U.ID
            """
        )

        posts = []
        comments_by_post = {}

        # Process the results into a structured dictionary
        for row in posts_with_comments:
            # Prepare the post details
            if not any(p["postID"] == row["postID"] for p in posts):
                posts.append({
                    "postID": row["postID"],
                    "imageUrl": row["imageUrl"],
                    "userID": row["userID"],
                    "handler": row["handler"],
                    "songName": row["songName"],
                    "songUrl": row["songUrl"],
                    "postDate": row["postDate"],
                    "timeElapse": time_ago(datetime.now(timezone.utc) - datetime.strptime(
                        row["postDate"], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc))
                })

            # If the post has comments, add them to a dictionary based on postID
            # Ensuring the comment exists (non-null content)
            if row["commentContent"]:
                comment = {
                    "commentUserID": row["commentUserID"],
                    "content": row["commentContent"],
                    "createdDate": row["commentCreatedDate"],
                    "userName": row["commentUserName"],
                    "avatar": row["commentAvatar"],
                    "timeElapse": time_ago(datetime.now(timezone.utc) - datetime.strptime(
                        row["commentCreatedDate"], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc))
                }

                # Collect the comments by postID
                if row["postID"] not in comments_by_post:
                    comments_by_post[row["postID"]] = []
                comments_by_post[row["postID"]].append(comment)

        # Pass comments grouped by post
        return render_template("index.html", posts=posts, comments=comments_by_post)

    if request.method == "POST":
        # Handle comment submission
        comment_content = request.form.get("commentInput")
        post_id = request.form.get("postID")  # postID hidden field from form

        print(comment_content + " ----- " + post_id)
        if comment_content and post_id:
            # Assuming user is logged in and user_id is in session
            user_id = session["user_id"]

            # Insert the new comment into the database
            db.execute(
                "INSERT INTO Comment (postID, userID, content, createdDate) VALUES (?, ?, ?, ?)",
                post_id, user_id, comment_content, datetime.now(
                    timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            )

        # After posting the comment, redirect to the home page (or the current page)
        return redirect("/")


@application.route("/profile", methods=["GET", "POST"])
def profile():
    if request.method == "GET":
        postsFromDB = db.execute(
            "SELECT Post.ID as postID, Post.title as postTitle, Post.imageUrl as imageUrl, User.ID as userID, User.handler, Song.songName, Song.songUrl, Post.createdDate as postDate FROM Post JOIN Song, User ON Post.songID = Song.ID AND User.ID = Post.userID WHERE Post.userID = ?", session["user_id"])

        print("Posts in Profile: ", postsFromDB)
        user_info = db.execute(
            "SELECT name, email, handler, imageUrl FROM User WHERE ID =  ?", session["user_id"])

        # print("CURRENT USER :", user)
        # user_info = db.execute(
        # " SELECT * FROM User INNER JOIN Profile ON User.ID=Profile.UserID WHERE User.ID = ?", session["user_id"])
        # print("USER INFO :", user_info)
        username = user_info[0]["handler"]
        image_url = user_info[0]["imageUrl"]

        if not image_url:
            image_url = "../static/avatar.jpeg"

        followings = db.execute(
            " SELECT * FROM Followers WHERE FollowerID = ?", session["user_id"])
        followers = db.execute(
            " SELECT * FROM Followers WHERE FollowingID = ?", session["user_id"])

        return render_template("profile.html", username=username, image_url=image_url, posts=postsFromDB)
    else:
        songUrl = request.form.get("post-songLink")
        slashCounter = 0
        firstIndex = 0
        secondIndex = 0
        for index, char in enumerate(songUrl):
            if slashCounter < 5 and char == "/":
                slashCounter += 1
                firstIndex = index + 1
            if char == "?":
                secondIndex = index - 1
        print(f"Index: 1: {firstIndex} - 2:{secondIndex}")
        print(f"CHAR: 1: {songUrl[firstIndex]} - 2:{songUrl[secondIndex]}")

        songId = songUrl[firstIndex:secondIndex+1]

        return render_template("profile.html")


@application.route("/friends", methods=["GET", "POST"])
def friendPage():
    if request.method == "GET":
        followingUsers = db.execute(
            "SELECT * FROM Followers JOIN Profile ON Followers.FollowerID = Profile.UserID WHERE FollowingID =  ?", session["user_id"])
        # print(followingUsers)

        followerUsers = db.execute(
            "SELECT * FROM Followers JOIN Profile ON Followers.FollowingID = Profile.UserID WHERE FollowerID =  ?", session["user_id"])
        print(followerUsers)
    return render_template("friends.html", followingUsers=followingUsers, followerUsers=followerUsers)


@application.route("/login", methods=["GET", "POST"])
def signIn():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("handler"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM User WHERE handler = ?",
                          request.form.get("handler"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["password"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["ID"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")
    # if request.method == "POST":
    #     email = request.form.get("email")
    #     password = request.form.get("password")
    #     print("Name Input after submit: ", email)
    #     print("Pass Input after submit: ", password)

    #     # check if email exists
    #     email_check = db.execute("SELECT * FROM User WHERE email=?", email)
    #     if not email_check:
    #         print("Email is wrong")
    #         return render_template("index.html")

    #     # check password is matched
    #     password_check = db.execute("SELECT * FROM User WHERE email=? AND password=?", email, password)
    #     if not password_check:
    #         print("Password is wrong")
    #         return render_template("index.html")

    #     return render_template("index.html")
    # # Validate submission
    # email = request.form.get("email")
    # password = request.form.get("password")
    # print("Name Input before: ", email)
    # print("Pass Input before: ", password)
    # return render_template("login.html")


@application.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Validate submission
        name = request.form.get("name")
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Query database for username
        rows = db.execute("SELECT * FROM User WHERE handler = ?", username)

        # Ensure password == confirmation
        if not (password == confirmation):
            return apology("the passwords do not match", 400)

        # Ensure password not blank
        if password == "" or confirmation == "" or username == "":
            return apology("input is blank", 400)

        # Ensure username does not exists already
        if len(rows) == 1:
            return apology("username already exist", 400)
        else:

            hashcode = generate_password_hash(
                password, method='pbkdf2:sha256', salt_length=8)
            db.execute("INSERT INTO User (handler, password, name, email) VALUES(?, ?, ?, ?)",
                       username, hashcode, name, email)

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")


# run the application.
if __name__ == "__main__":
    # Setting debug to True enables debug output. This line should be
    # removed before deploying a production application.
    application.debug = True
    application.run()
