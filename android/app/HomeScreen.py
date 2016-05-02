from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty, StringProperty


class HomeScreen(BoxLayout):
    
    def __init__(self):
        from kivy.lang import Builder
        Builder.load_file('HomeScreen.kv')

    title = StringProperty('Tribler')

    top_pane = ObjectProperty()
    content_pane = ObjectProperty()

    def go_favs(self):
        print self

    def go_recent(self):
        print self

    def go_mine(self):
        print self

    def go_search(self):
        print self

    def go_back(self):
        print self

    def add_video(self):
        print self