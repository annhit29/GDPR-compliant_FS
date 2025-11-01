class GlobalApp:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalApp, cls).__new__(cls)
            cls._instance.twit = None 
        return cls._instance  

app_global = GlobalApp()