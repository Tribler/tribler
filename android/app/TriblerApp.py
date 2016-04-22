from kivy.app import App
from kivy.core.window import Window

from jnius import autoclass


class TriblerApp(App):

    def run(self):
        self.kv_file = 'gui/TriblerApp.kv'
        return App.run(self)

    def build(self):
        Window.bind(on_key_down=self.on_key_down)
        return App.build(self)

    def on_key_down(self, window, keycode, scancode, text, modifiers):
        print self
        print window
        print keycode
        print scancode
        print text
        print modifiers

        if keycode == 1073742094: # Back
            print 'Back'
            return True
       
        elif keycode == 1073741942: # Menu
            print 'Menu'
            return True

        return False


    def start_service_triblerd(self):
        service = autoclass('org.tribler.android.ServiceTriblerd')
        mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
        argument = ''
        service.start(mActivity, argument)


    def on_start(self):
        '''Event handler for the `on_start` event which is fired after
        initialization (after build() has been called) but before the
        application has started running.
        '''
        self.start_service_triblerd()

    def on_stop(self):
        '''Event handler for the `on_stop` event which is fired when the
        application has finished running (i.e. the window is about to be
        closed).
        '''
        pass

    def on_pause(self):
        '''Event handler called when Pause mode is requested. You should
        return True if your app can go into Pause mode, otherwise
        return False and your application will be stopped (the default).

        You cannot control when the application is going to go into this mode.
        It's determined by the Operating System and mostly used for mobile
        devices (android/ios) and for resizing.

        The default return value is False.

        .. versionadded:: 1.1.0
        '''
        return True

    def on_resume(self):
        '''Event handler called when your application is resuming from
        the Pause mode.

        .. versionadded:: 1.1.0

        .. warning::

            When resuming, the OpenGL Context might have been damaged / freed.
            This is where you can reconstruct some of your OpenGL state
            e.g. FBO content.
        '''
        pass
