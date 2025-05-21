from website import create_app, create_admin
import os

app = create_app()

with app.app_context():
    create_admin()

#create_admin()
if __name__ == '__main__':
    app.run(debug=True) #this is for local testing
    
    # For google cloud run
    #port = int(os.environ.get("PORT", 8080))
    #app.run(host="0.0.0.0", port=port)