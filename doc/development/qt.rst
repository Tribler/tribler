
Our GUI uses QT toolkit. It can be quite tricky at times. Also, PyQt have LOTS of bugs, so be warned! 
For the beginner, the best way to develop QT is to just copy-paste stuff around, looking for examples in our codebase.




Do's and don'ts of QT design
============================

There are three "don'ts" in QT design:
 * **Don't set CSS in the code**. Instead, **do** set it in the widget ``.ui``-file
 * **Don't set it on individual widgets** unless absolutely neccesary. Instead, **do** set it on the highest parent widget, which is the main Tribler window in our case. CSS will do the rest
 * **Don't copy-paste the stylesheets**. Instead, **do** try to move as much CSS as possible to the highest possible parent widget and **subclass** the widgets in Qt Creator.
 
Do's:
 * **Do** connect signals using Tribler ``connect()`` procedure. It is much safer and easy this way.
