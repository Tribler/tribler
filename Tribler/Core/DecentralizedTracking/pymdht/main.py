import kivy
kivy.require('1.0.6')

from kivy.app import App
from kivy.uix.button import Button

import core.identifier as identifier
import core.node as node
import core.pymdht as pymdht
import plugins.lookup_a4 as lookup_m_mod
import plugins.routing_nice_rtt as routing_m_mod
import core.exp_plugin_template as exp_mod

dht = None


def _on_peers_handler(button, peers, node_):
    if peers:
        msg = 'got %d peers\n' % len(peers)
    else:
        msg = 'END OF LOOKUP\n'
    button.text += msg


class LookupButton(Button):

    def __init__(self):
        Button.__init__(self, text='DHT lookup\n')
    
    def on_press(self):
        dht.get_peers(
            self, identifier.Id('e936e73881ee1920b8edbd263d001fffed424c5f'),
            _on_peers_handler)


class MyApp(App):
    def build(self):
        return LookupButton()

    
if __name__ in ('__android__', '__main__'):
    my_addr = ('127.0.0.1', 7000)
    my_node = node.Node(my_addr, identifier.RandomId(),
                        version=pymdht.VERSION_LABEL)
    dht = pymdht.Pymdht(my_node, '.',
                        routing_m_mod, lookup_m_mod,
                        exp_mod,
                        None,
                        0,
                        False)
    MyApp().run()
