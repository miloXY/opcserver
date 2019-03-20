from flask import (render_template, flash, url_for, jsonify,request,redirect)
from index import app,db
from index.models import Server,Object, Variable
from index.forms import ServerCreateForm,ObjectCreateForm,VariableCreateForm
from . import utils
from myserver import MyServer
from myplc import MyPlc
from snap7.snap7exceptions import Snap7Exception

global ms,mp
ms = MyServer()
mp = MyPlc()

ctrl = Control()

@app.route("/")
def home():
    servers = Server.query.all()
    form = ServerCreateForm()
    return render_template('index.html',form=form,servers=servers)

@app.route("/",methods= ['POST','GET'] )
def create_server():
    form = ServerCreateForm()
    if form.validate_on_submit():
        server = Server( name=form.server_name.data, endpoint_url=form.endpoint_url.data,namespace=form.namespace.data )
        db.session.add(server)
        db.session.commit()
        resp = {
            'message' : '{} Created Successfully'.format(form.server_name.data),
            'servers' : Server.query.all()
        }
        return redirect(url_for('home'))

    return jsonify(data=form.errors)

@app.route("/server/delete/<serverid>",methods= ['POST'] )    
def delete_server( serverid ):
    server = Server.query.get( serverid )
    servername = server.name
    db.session.delete(server)
    db.session.commit()
    flash('{} Deleted SUccessfully'.format(servername), 'success')
    return redirect(url_for('create_server'))


@app.route("/server/<serverid>",methods= ['GET'] )
def server_populate(serverid):
    server = Server.query.get( serverid )
    objform = ObjectCreateForm()
    varform = VariableCreateForm()
    objects = server.objects
    varform.var_object.choices = utils.selectVals(objects)
    # objform.parent_object.choices = selectVals(objects)
    # vars = server.objects
    return render_template('server.html',
             objects=objects,
             server=server, 
             objform = ObjectCreateForm(),
             varform=varform
    )
@app.route("/start_server/<serverid>",methods=['POST'])
def start_server(serverid):
    global ms
    global mp
    if request.method=='POST' and request.form: 

        server = Server.query.get(request.form['server'])
        plc_ip = request.form['plc_ip']
        try:
            if isinstance(ms, MyServer) is False:

        except NameError as nexp:
            return 
            ms = MyServer(server.id)
        try:
            ms.opc_server.start()
            if plc_ip is not None:
                mp = MyPlc( server.id, plc_ip )
            else:
                mp = MyPlc( server.id )
        except OSError as err:
            return jsonify({ "danger" : "The address and port at {} are being used by sbd/sth else".format(server.endpoint_url) })
        except Snap7Exception as snap:            
            return jsonify({ 'danger' :[ x if len(str(x)) > 5 else None for x in snap.args ]})
        except Exception as exp:
            return jsonify( { 'danger': [ x if len(str(x)) > 5 else None for x in exp.args ]} ) 
        else:
            return jsonify({ "success": "SERVER: {}, started at: {}".format(server.name,server.endpoint_url)} )     
    else:
        return jsonify("Web Server Error")


@app.route("/stop_server/<serverid>",methods=['GET'])
def stop_server(serverid):
    global ms
    global mp
    ms.opc_server.stop()
    mp.kill_threads()
    del ms, mp
    return jsonify({"info":"Server Stoped"})

@app.route("/create_object",methods= ['POST'] )
def create_object():
    objform = ObjectCreateForm()
    
    serverobj = Server.query.get(objform.server.data)
    if request.method=='POST' and request.form:        
        obj = Object(   name = request.form['object_name'],
                        parent_id = request.form['parent_object'] if request.form['parent_object'] else None,
                        server = Server.query.get(request.form['server']) 
                    )
        db.session.add(obj)
        db.session.commit()
        return redirect( url_for('server_populate',serverid=serverobj.id) )
    else:    
        flash('Could not create {} object'.format(objform.object_name))
        return redirect(url_for('server_populate',serverid=serverobj.id))

@app.route("/create_variable",methods= ['POST'] )
def create_variable():
    varform = VariableCreateForm()
    # return jsonify(varform.object.data)
    obj = Object.query.get(varform.var_object.data)
    if utils.custom_validation( varform.data ):
        var = Variable( name=varform.name.data,
                        type=varform.var_type.data,
                        writable=varform.writable.data,
                        tag_id=varform.tag.data,
                        value=varform.value.data,
                        object=Object.query.get(varform.var_object.data),
                         )
        db.session.add(var)
        db.session.commit()
        resp={
            'message' : '{} Created Successfully'.format(var.name),
            'object'  : varform.data
        }
        return redirect( url_for('server_populate',serverid=obj.server.id) )
    else:    
        flash('Could not create {} Variable'.format(varform.name.data))
        return redirect(url_for('server_populate',serverid=obj.server.id))
        # return jsonify(request.data)

@app.route("/variables/<var_id>/delete",methods= ['GET'] )
def delete_var(var_id):
    var = Variable.query.get(var_id)
    db.session.delete(var)
    db.session.commit()
    return jsonify("Deleted Successfully")

@app.route("/delete_object",methods= ['POST'] )
def delete_object():
    obj = Object.query.get(request.form['object_id'])
    objName = obj.name
    server_id = request.form['server_id']

    db.session.delete( obj )
    db.session.commit()
    flash('{} Deleted SUccessfully'.format(objName), 'success')
    return redirect(url_for('server_populate',serverid=server_id))
    
def server_start_util(server, plc_ip ,myserv, myplc):
    danger = []
    info = []
    if isinstance(myserv,MyServer):
        # Check if OPC Server is running
        if isOpen(server.endpoint_url):
            info.append[ "Server running at opc.tcp://"+server.endpoint_url ]
            try:
                # Connect to PLC 
                if plc_ip is not None:
                    myplc = MyPlc( serverid,plc_ip )
                else:
                    myplc = MyPlc( serverid )
                info.append(["PLC Connected"])
            except:
                danger.append["Couldn't connect top plc at: "+plc_ip ]

        else:
            danger.append([ "Server failed to start at opc.tcp://"+server.endpoint_url+". Check log file" ])
            
    else:
        # try:
        myserv = MyServer( server.id )   
            # server_start_util(server, plc_ip ,myserv, myplc, MYSERV, MYPLC)
        # except:
        #     danger.append(["Couldn't launch server"])
    
    msgs = {
        'danger' : danger,
        'info' : info,
    }
    return myserv, myplc, msgs  