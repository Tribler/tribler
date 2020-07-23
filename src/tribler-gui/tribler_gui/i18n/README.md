# Internationalization

This app uses the QT multi language feature to provide internationalization. 

## Improving a translation

If you find a mistake for an existing language, a missing translation or any other problem, you can help us. Just find right `<source>` key in the respective TS file and change the value of the `<translation>` key.

## New translations

If you want to translate Tribler to a new language, you need to create a new TS file. The file is named according to [rfc1766](https://tools.ietf.org/html/rfc1766.html) (pt_BR, for example). You can easily create a new file by adding a new line in the script `extract-messages` and then running it.

Running `extract-messages` is going to update all the existing translatable strings in Tribler, creating new keys and marking obsolete ones. *Run this when you change the interface and need to update translations.*

## Releasing a new translation

QT expects a binary file to load new translations. So we need a tool to convert a .ts file to a .qm file. That tool is encapsulated in the `update_translations` script. Change the translations, run the scripts and Voilà, nueva traducción disponible!

You need to remove the tag `type="unfinished"` once you consider the translation finished and then run the `update_translations` script. QT can handle partially translated TS files, so don't shy away if you cannot translate 100% of the app. 
