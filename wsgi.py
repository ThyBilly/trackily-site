from app import create_app

application = create_app()
app = application  # This ensures compatibility with both uWSGI and Flask development server

if __name__ == '__main__':
    app.run()