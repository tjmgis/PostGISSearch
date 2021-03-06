# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PostGISSearch
                                 A QGIS plugin
 Plugin for searching data in PostGIS Database
                              -------------------
        begin                : 2014-03-07
        copyright            : (C) 2014 by Tim Martin
        email                : tjmgis@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from PyQt4.QtSql import *
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from postgissearchdialog import PostGISSearchDialog
import os.path
from ConfigParser import SafeConfigParser

from qgis.core import *
from qgis.gui import *
from qgis.utils import *
from qgis.core import QgsGeometry, QgsPoint


class PostGISSearch():

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        localePath = os.path.join(self.plugin_dir, 'i18n', 'postgissearch_{}.qm'.format(locale))

        if os.path.exists(localePath):
            self.translator = QTranslator()
            self.translator.load(localePath)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

    def initGui(self):
        # Create action that will start plugin configuration
        self.action = QAction(
            QIcon(":/plugins/postgissearch/postgissearch_logo.png"),
            u"PostGIS Search", self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.run)

        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&PostGIS Search", self.action)

    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&PostGIS Search", self.action)
        self.iface.removeToolBarIcon(self.action)


    # run method that performs all the real work
    def run(self):
        #the following code reads the configuration file which setups the plugin to search in the correct database, table and method
        plugin_path = os.path.dirname(os.path.realpath(__file__))

        fname = os.path.join(plugin_path, "postgis.ini")

        if os.path.exists(fname):
            pass
        else:
            iface.messageBar().pushMessage("Error", "No config file found", level=QgsMessageBar.CRITICAL, duration=5)

        parser = SafeConfigParser()

        try:
            parser.read(fname)
            self.postgisdatabase = parser.get('postgis', 'postgisdatabase')
            self.postgisusername = parser.get('postgis', 'postgisusername')
            self.postgispassword = parser.get('postgis', 'postgispassword')
            self.postgishost = parser.get('postgis', 'postgishost')
            self.postgisport = parser.get('postgis', 'postgisport')
            self.postgisschema = parser.get('postgis', 'postgisschema')
            self.postgistable = parser.get('postgis', 'postgistable')
            self.postgissearchcolumn = parser.get('postgis', 'postgissearchcolumn')
            self.postgisdisplaycolumn = parser.get('postgis', 'postgisdisplaycolumn')
            self.postgisgeomname = parser.get('postgis', 'postgisgeomname')
            self.searchmethod = parser.get('postgis', 'searchmethod')
        except:
            iface.messageBar().pushMessage("Error", "Something wrong in the config file", level=QgsMessageBar.CRITICAL, duration=5)


        #declare the dlg
        self.dlg = PostGISSearchDialog()
        # show the dialog
        self.dlg.show()

        #Info box explaining the problems using SQL query.
        if self.searchmethod == "SQL":
            QMessageBox.warning(None, "Info", "Querying a large dataset by SQL search method may cause the search box to become unresponsive. So type slowly and wait for results to appear. If possible create a Full Text Search (FTS) column and change the search method.")

        #tie the line edit to the function
        self.dlg.ui.searchText.textChanged.connect(self.addPostGISLayer)

        # Run the dialog event loop
        result = self.dlg.exec_()


    #following function takes the contents of the line edit and uses it to query the declared database
    def addPostGISLayer(self, string):
        if (len(string) > 4) or (" " in string):
                uri = QgsDataSourceURI()
                # set host name, port, database name, username and password
                uri.setConnection(self.postgishost, self.postgisport, self.postgisdatabase, self.postgisusername, self.postgispassword)

               #need a different SQL query based on the search method declared in the postgis.ini file
                if self.searchmethod == 'SQL':
                    querystring = (string + "%")
                    sql = """SELECT %s, ST_X(%s) as x, ST_Y(%s) as y from %s.%s WHERE LOWER(%s) LIKE LOWER('%s') LIMIT 100"""%(self.postgisdisplaycolumn, self.postgisgeomname, self.postgisgeomname, self.postgisschema, self.postgistable, self.postgissearchcolumn, querystring)

                elif self.searchmethod == 'FTS':
                    sql = """SELECT %s, ST_X(%s) as x, ST_Y(%s) as y FROM %s.%s WHERE %s @@ plainto_tsquery('english', '%s') LIMIT 100"""%(self.postgisdisplaycolumn, self.postgisgeomname, self.postgisgeomname, self.postgisschema, self.postgistable, self.postgissearchcolumn, string)

                else:
                    iface.messageBar().pushMessage("Error", "Wrong search method declared in config file", level=QgsMessageBar.CRITICAL, duration=5)

                #specify the type of database to query - in principla this could be changed to other databases
                self.db = QSqlDatabase.addDatabase('QPSQL')

                # check to see if it is valid
                if self.db.isValid():
                    self.db.setHostName(uri.host())
                    self.db.setDatabaseName(uri.database())
                    self.db.setPort(int(uri.port()))
                    self.db.setUserName(uri.username())
                    self.db.setPassword(uri.password())
                    # open (create) the connection
                    if self.db.open():
                        #setup model and run the query and then set the model to the results
                        self.projectModel = QSqlQueryModel()
                        self.projectModel.setQuery(sql,self.db)
                        self.dlg.ui.tableView.setModel(self.projectModel)
                        #close connection to database
                        self.db.close()
                        self.db.removeDatabase('QPSQL')
                        #tweak the table based on the results
                        self.dlg.ui.tableView.resizeColumnsToContents()
                        #tie table to function for adding point to map canvas
                        self.dlg.ui.tableView.selectionModel().currentChanged.connect(self.cellClicked)

    #the following function runs when the user clicks a row of the search results
    def cellClicked(self):
        iface.mapCanvas().refresh()

        #get the selected row from table view
        if self.dlg.ui.tableView.currentIndex():
            index = self.dlg.ui.tableView.currentIndex().row()

            #need just one attribute for the label, this will be the first attribute if more than one is returned by the SQL query
            if "," in self.postgisdisplaycolumn:
                labelcolumn = self.postgisdisplaycolumn.split(",")[0]
            else:
                labelcolumn = self.postgisdisplaycolumn

            #setup the x and y variables which are used to create a memory point on the map canvas
            self.x = self.projectModel.record(index).value("x")
            self.y = self.projectModel.record(index).value("y")
            self.label = str(self.projectModel.record(index).value(labelcolumn))

        canvas = self.iface.mapCanvas()
        dest_crs = canvas.mapRenderer().destinationCrs()

        #create memory layer for the new point
        self.pinLayer =  QgsVectorLayer("Point?&field=Description:string(120)&field=X_Coordinate:double&field=Y_Coordinate:double&index=yes", self.label, "memory")
        self.provider = self.pinLayer.dataProvider()
        QgsMapLayerRegistry.instance().addMapLayer(self.pinLayer)

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPoint(QgsPoint(self.x,self.y)))
        #depending on the version of QGIS adding the feature to the memory layer is different
        if QGis.QGIS_VERSION_INT > 10800:
            feature.setAttributes([self.label, self.x, self.y])
            self.pinLayer.startEditing()
            self.pinLayer.addFeature(feature, True)
            self.pinLayer.commitChanges()
        else:
            feature.setAttributeMap( {0 : QVariant(self.description),
                1 : QVariant(self.x),
                2 : QVariant(self.y)})
            self.provider.addFeatures([feature])
            self.pinLayer.updateExtents()

        #based on the feature move and scale the map accodingly
        scale = 1200
        rect = QgsRectangle(float(self.x)-scale,float(self.y)-scale,float(self.x)+scale,float(self.y)+scale)
        canvas.setExtent(rect)
        canvas.refresh()

        #close the dialogue do user can see map automcatically
        self.dlg.close()


if __name__ == "__main__":
    pass