from website import create_app, create_admin


app = create_app()

with app.app_context():
    create_admin()

#create_admin()
if __name__ == '__main__':
    app.run(debug=True)
