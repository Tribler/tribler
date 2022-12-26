*******
Tribler
*******
|Pytest| |docs| |Codacy| |Coverage| |contributors| |pr_closed| |issues_closed|

|python_3_8| |python_3_9|

|downloads_7_0| |downloads_7_1| |downloads_7_2| |downloads_7_3| |downloads_7_4|
|downloads_7_5| |downloads_7_6| |downloads_7_7| |downloads_7_8| |downloads_7_9|
|downloads_7_10| |downloads_7_11|

|doi| |openhub| |discord|

*Hacia un Bittorrent anónimo e imposible de cerrar.*

Utilizamos nuestra propia red Tor para la descarga anónima de torrents..
Implementamos y mejoramos las especificaciones del `protocolo Tor <https://github.com/Tribler/tribler/wiki/Anonymous-Downloading-and-Streaming-specifications>`_.
Tribler incluye nuestra propia red de enrutamiento cebolla similar a Tor con servicios ocultos basados en
sembrado y `cifrado de extremo a extremo <https://github.com/Tribler/tribler/wiki/Anonymous-Downloading-and-Streaming-specifications>`_.

Tribler pretende dar acceso anónimo a los contenidos. Intentamos que la privacidad, la criptografía robusta y la autenticación sean la norma en Internet.

Durante los últimos 11 años hemos estado construyendo un sistema Peer-to-Peer muy robusto.
Hoy Tribler es robusto: "la única forma de acabar con Tribler es acabar con Internet" (pero un simple error de software podría acabar con todo).

Obtener la última versión
=========================

Haga clic aquí <https://github.com/Tribler/tribler/releases/latest>`__ y descargue el último paquete para su SO.

Obtener soporte
===============

Si ha encontrado un error o tiene una petición de funcionalidad, asegúrese de leer `nuestra página de contribuciones 
<http://tribler.readthedocs.io/en/latest/contributing.html>`_ y luego `abra una incidencia <https://github.com/Tribler/tribler/issues/new>`_. 
Le echaremos un vistazo lo antes posible.

Contribución
============

¡Las contribuciones son bienvenidas!
Si está interesado en contribuir con código o cualquier otra cosa, eche un vistazo a nuestra `página de contribuciones 
<http://tribler.readthedocs.io/en/latest/contributing.html>`_.
Eche un vistazo al `gestor de incidencias <https://github.com/Tribler/tribler/issues>`_ si busca inspiración :).


Cómo ejecutar Tribler desde el repositorio
##########################################

Apoyamos el desarrollo en Linux, macOS y Windows. Disponemos de documentación
escrita que le guiará en la instalación de los paquetes necesarios para
configurar un entorno de desarrollo Tribler.

* `Linux <http://tribler.readthedocs.io/en/latest/development/development_on_linux.html>`_
* `Windows <http://tribler.readthedocs.io/en/latest/development/development_on_windows.html>`_
* `macOS <http://tribler.readthedocs.io/en/latest/development/development_on_osx.html>`_



Empaquetando Tribler
====================

Hemos escrito guías sobre cómo empaquetar Tribler para su distribución en varios sistemas.

* `Linux <http://tribler.readthedocs.io/en/latest/building/building.html>`_
* `Windows <http://tribler.readthedocs.io/en/latest/building/building_on_windows.html>`_
* `macOS <http://tribler.readthedocs.io/en/latest/building/building_on_osx.html>`_


Compatibilidad con Docker
=========================

Dockerfile se proporciona con el código fuente que se puede utilizar para construir la imagen docker.

Para construir la imagen docker:

.. code-block:: bash

    docker build -t triblercore/triblercore:latest .


Para ejecutar la imagen docker creada:

.. code-block:: bash

    docker run -p 20100:20100 --net="host" triblercore/triblercore:latest

Tenga en cuenta que, por defecto, la API REST está vinculada a localhost dentro del contenedor por lo que para
acceder a las APIs, la red debe estar configurada en host (--net="host").

Ya se puede acceder a las API REST en: http://localhost:20100/docs


**Docker Compose**

El núcleo de Tribler también puede iniciarse utilizando Docker Compose. Para ello, un archivo `docker-compose.yml` 
está disponible en el directorio raíz del proyecto.

Para ejecutar a través de docker compose:

.. code-block:: bash

    docker-compose up


Para ejecutar en modo independiente:

.. code-block:: bash

    docker-compose up -d


Para detener Tribler:

.. code-block:: bash

    docker-compose down


Póngase en contacto
===================

Nos gusta escuchar sus comentarios y sugerencias. Para ponerte en contacto con nosotros, puede unirse a `nuestro servidor Discord <https://discord.gg/UpPUcVGESe>`_ 
o crear un mensaje en `nuestros foros <https://forum.tribler.org>`_.


.. |jenkins_build| image:: http://jenkins-ci.tribler.org/job/Test_tribler_main/badge/icon
    :target: http://jenkins-ci.tribler.org/job/Test_tribler_main/
    :alt: Build status on Jenkins

.. |pr_closed| image:: https://img.shields.io/github/issues-pr-closed/tribler/tribler.svg?style=flat
    :target: https://github.com/Tribler/tribler/pulls
    :alt: Pull Requests

.. |issues_closed| image:: https://img.shields.io/github/issues-closed/tribler/tribler.svg?style=flat
    :target: https://github.com/Tribler/tribler/issues
    :alt: Issues

.. |openhub| image:: https://www.openhub.net/p/tribler/widgets/project_thin_badge.gif?style=flat
    :target: https://www.openhub.net/p/tribler

.. |downloads_7_0| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.0.2/total.svg?style=flat
    :target: https://github.com/Tribler/tribler/releases
    :alt: Downloads(7.0.2)

.. |downloads_7_1| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.1.3/total.svg?style=flat
    :target: https://github.com/Tribler/tribler/releases
    :alt: Downloads(7.1.3)

.. |downloads_7_2| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.2.2/total.svg?style=flat
    :target: https://github.com/Tribler/tribler/releases
    :alt: Downloads(7.2.2)

.. |downloads_7_3| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.3.2/total.svg?style=flat
    :target: https://github.com/Tribler/tribler/releases
    :alt: Downloads(7.3.2)

.. |downloads_7_4| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.4.1/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.4.1)

.. |downloads_7_5| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.5.1/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.5.1)

.. |downloads_7_6| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.6.1/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.6.1)

.. |downloads_7_7| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.7.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.7.0)

.. |downloads_7_8| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.8.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.8.0)

.. |downloads_7_9| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.9.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.9.0)

.. |downloads_7_10| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.10.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.10.0)

.. |downloads_7_11| image:: https://img.shields.io/github/downloads/tribler/tribler/v7.11.0/total.svg?style=flat
     :target: https://github.com/Tribler/tribler/releases
     :alt: Downloads(7.11.0)

.. |contributors| image:: https://img.shields.io/github/contributors/tribler/tribler.svg?style=flat
    :target: https://github.com/Tribler/tribler/graphs/contributors
    :alt: Contributors
    
.. |doi| image:: https://zenodo.org/badge/8411137.svg
    :target: https://zenodo.org/badge/latestdoi/8411137
    :alt: DOI number

.. |docs| image:: https://readthedocs.org/projects/tribler/badge/?version=latest
    :target: https://tribler.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. |discord| image:: https://img.shields.io/badge/discord-join%20chat-blue.svg
    :target: https://discord.gg/UpPUcVGESe
    :alt: Join Discord chat

.. |python_3_8| image:: https://img.shields.io/badge/python-3.8-blue.svg
    :target: https://www.python.org/

.. |python_3_9| image:: https://img.shields.io/badge/python-3.9-blue.svg
    :target: https://www.python.org/

.. |Pytest| image:: https://github.com/Tribler/tribler/actions/workflows/pytest.yml/badge.svg?branch=main
    :target: https://github.com/Tribler

.. |Codacy| image:: https://app.codacy.com/project/badge/Grade/35785b4de0b84724bffdd2598eea3276
   :target: https://www.codacy.com/gh/Tribler/tribler/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Tribler/tribler&amp;utm_campaign=Badge_Grade

.. |Coverage| image:: https://app.codacy.com/project/badge/Coverage/35785b4de0b84724bffdd2598eea3276
   :target: https://www.codacy.com/gh/Tribler/tribler/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Tribler/tribler&amp;utm_campaign=Badge_Coverage
