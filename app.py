# -*- coding: utf-8 -*-
from flask import Flask, request, redirect, session, render_template_string, send_file
import sqlite3, io
from datetime import datetime
from fpdf import FPDF
import pandas as pd

app = Flask(__name__)
app.secret_key = 'seiem_v14_completo'
DB = 'inventario_seiem.db'

def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db=get_db()
    db.execute("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, rol TEXT, oficina TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS oficinas (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
    db.execute("CREATE TABLE IF NOT EXISTS bienes (id INTEGER PRIMARY KEY AUTOINCREMENT, no_inventario TEXT UNIQUE, descripcion TEXT, marca TEXT, modelo TEXT, serie TEXT, estado TEXT, resguardatario TEXT, oficina TEXT, fecha_alta TEXT, en_baja INTEGER DEFAULT 0)")
    db.execute("CREATE TABLE IF NOT EXISTS solicitudes (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, bien_id INTEGER, no_inventario TEXT, descripcion TEXT, oficina_origen TEXT, oficina_destino TEXT, resguardatario_actual TEXT, resguardatario_nuevo TEXT, motivo TEXT, estado TEXT, fecha TEXT, usuario_solicita TEXT)")
    db.execute("""
CREATE TABLE IF NOT EXISTS bienes_propios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folio_num TEXT,
    folio TEXT,
    fecha_solicitud TEXT,
    fecha_respuesta TEXT,
    fecha TEXT,
    nombre_completo TEXT,
    rfc TEXT,
    curp TEXT,
    oficina TEXT,
    departamento TEXT,
    descripcion_bien TEXT,
    bienes_json TEXT,
    marca TEXT,
    modelo TEXT,
    serie TEXT,
    color TEXT,
    factura TEXT,
    valor TEXT,
    motivo TEXT,
    estatus TEXT,
    usuario_solicita TEXT,
    usuario_solicitante TEXT,
    solicitante TEXT,
    observaciones TEXT
)
""")
    cur=db.execute("SELECT * FROM usuarios WHERE username='admin'")
    if not cur.fetchone(): db.execute("INSERT INTO usuarios VALUES (NULL,'admin','admin123','admin','Direccion General')")
    c=db.execute("SELECT COUNT(*) as c FROM oficinas").fetchone()['c']
    if c==0:
        for o in []:
            try: db.execute("INSERT INTO oficinas (nombre) VALUES (?)",(o,))
            except: pass
    # CANDADO: no puede haber 2 solicitudes pendientes con el mismo no_inventario
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_no_pendiente ON solicitudes(no_inventario) WHERE estatus='PENDIENTE'")
    except:
        pass
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_no_pendiente2 ON solicitudes(no_inventario) WHERE estatus='POR AUTORIZAR'")
    except:
        pass
    db.commit();db.close()
init_db()

def clean(v):
    if v is None: return ''
    try:
        if pd.isna(v): return ''
    except: pass
    s=str(v).strip()
    if s.lower() in ('nan','none','nat',''): return ''
    return s

TODAS = """
<a href="/dashboard">INICIO</a>
<a href="/reportes">REPORTES</a>
<a href="/resguardos">RESGUARDOS</a>
<a href="/graficas">GRAFICAS</a>
<a href="/cambio_resguardatario">CAMBIO</a>
<a href="/bajas">BAJAS</a>
<a href="/verificacion">VERIFICACION</a>
<a href="/mis_movimientos">MIS MOVIMIENTOS</a>
<a href="/usuarios">USUARIOS</a>
<a href="/oficinas">OFICINAS</a>
<a href="/bienes_propios" style="background:#E65100;color:white;padding:4px 10px;border-radius:12px">\U0001F4E6 BIENES PROPIOS</a>
"""
SOLO_USUARIO = """
<a href="/reportes">REPORTES</a>
<a href="/resguardos">RESGUARDOS</a>
<a href="/cambio_resguardatario">CAMBIO RESGUARDATARIO</a>
<a href="/bajas">BAJAS</a>
<a href="/mis_movimientos">MIS MOVIMIENTOS SOLICITADOS</a>
<a href="/bienes_propios" style="background:#E65100;color:white;padding:4px 10px;border-radius:12px">\U0001F4E6 BIENES PROPIOS</a>
"""

def render_page(content):
    u = session.get('username','') or ''
    ofi = session.get('oficina','') or ''
    rol = (session.get('rol','') or 'usuario').lower()
    rol_txt = str(rol).upper()
    menu_html = TODAS if rol == 'admin' else SOLO_USUARIO
    return render_template_string("""
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>SEIEM V14</title>
<style>body{margin:0;padding:0;box-sizing:border-box;background:#f3f3f0;font-family:Arial}.topbar{background:white;display:flex;justify-content:space-between;padding:10px 15px;border-bottom:4px solid #691C32;position:sticky;top:0;z-index:10;align-items:center}.menu a{margin:0 5px;text-decoration:none;color:#691C32;font-weight:bold;font-size:11px}.userbox{font-size:12px}</style>
</head><body>
<div class="topbar"><div><b>SEIEM - PADRON D.E.E.</b></div><div class="menu">"""+menu_html+"""</div><div class="userbox">"""+u+""" | """+ofi+""" <span style="background:#FFD700;color:#691C32;padding:2px 6px;border-radius:8px;margin-left:5px">"""+rol_txt+"""</span> <a href="/logout" style="background:#691C32;color:white;padding:4px 10px;border-radius:8px;text-decoration:none;margin-left:10px;font-weight:bold">SALIR</a></div></div>
<div style="padding:15px;max-width:1150px;margin:auto">"""+content+"""</div></body></html>""")
def solo_admin(f):
    from functools import wraps
    @wraps(f)
    def deco(*a,**k):
        if (session.get('rol','') or '').lower() != 'admin':
            return redirect('/reportes')
        return f(*a,**k)
    return deco
('/')
def idx(): return redirect('/dashboard') if 'username' in session else redirect('/login')


@app.route('/login', methods=['GET','POST'])
def login():
    db=get_db()
    if request.method=='POST':
        u=request.form.get('username','').strip().lower()
        p=request.form.get('password','').strip()
        user=db.execute("SELECT * FROM usuarios WHERE username=? AND password=?",(u,p)).fetchone()
        db.close()
        if user:
            session['username']=user['username']
            try: session['rol']=user['rol'] or 'usuario'
            except: session['rol']='usuario'
            try: session['oficina']=user['oficina'] or 'ACADEMICA'
            except: session['oficina']='ACADEMICA'
            if (session['rol'] or '').lower() == 'admin':
                return redirect('/dashboard')
            else:
                return redirect('/reportes')
        return render_template_string("<div style='min-height:100vh;display:flex;justify-content:center;align-items:center;background:#f6f3f0'><div style='background:white;padding:25px;border-radius:12px;text-align:center'><h3 style='color:red'>Usuario o contraseña incorrecta</h3><a href='/login' style='background:#691C32;color:white;padding:10px 20px;border-radius:8px;text-decoration:none'>Intentar de nuevo</a></div></div>")
    db.close()
    ok=request.args.get('ok')
    return render_template_string("""
    <div style="min-height:100vh;background:#f6f3f0;display:flex;justify-content:center;align-items:center">
      <div style="background:white;padding:25px;border-radius:15px;box-shadow:0 4px 20px rgba(0,0,0,0.2);width:100%;max-width:380px">
        <h2 style="color:#691C32;text-align:center">SEIEM - PADRON 737</h2>
        {% if ok %}<p style="background:#e8f5e9;color:#2e7d32;padding:10px;border-radius:8px;text-align:center">¡Registro exitoso! Ya puedes entrar</p>{% endif %}
        <form method="post">
          <input name="username" required placeholder="Usuario" style="width:100%;padding:12px;border:2px solid #691C32;border-radius:8px;margin-bottom:10px">
          <input name="password" type="password" required placeholder="Contraseña" style="width:100%;padding:12px;border:2px solid #691C32;border-radius:8px;margin-bottom:15px">
          <button style="width:100%;padding:13px;background:#691C32;color:white;border:none;border-radius:8px;font-weight:bold">ENTRAR</button>
        </form>
        <p style="text-align:center;margin-top:15px;font-size:13px">¿No tienes cuenta?<br>
        <a href="/registro" style="background:#2e7d32;color:white;padding:10px 15px;border-radius:8px;text-decoration:none;display:inline-block;margin-top:8px;font-weight:bold">REGISTRARSE AQUÍ</a></p>
      </div>
    </div>
    """, ok=ok)

@app.route('/registro', methods=['GET','POST'])
def registro():
    db=get_db()
    msg=""
    # Candado a nivel base de datos
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_oficina_unica_usuario ON usuarios(oficina) WHERE LOWER(rol)='usuario'")
        db.commit()
    except: pass

    try: 
        oficinas=db.execute("SELECT nombre FROM oficinas ORDER BY nombre").fetchall()
    except: 
        oficinas=[]

    if request.method=='POST':
        usuario=request.form.get('usuario_reg','').strip().lower()
        password=request.form.get('password_reg','').strip()
        nombre=request.form.get('nombre','').strip().upper()
        oficina=request.form.get('oficina','').strip()
        if not usuario or not password or not nombre or not oficina:
            msg="Llena todos los campos"
        else:
            try:
                # 1. Checa si usuario ya existe
                existe_user=db.execute("SELECT id FROM usuarios WHERE username=?",(usuario,)).fetchone()
                if existe_user: 
                    msg="Ese usuario ya existe"
                else:
                    # 2. BLOQUEO: Checa si oficina ya tiene usuario
                    existe_ofi=db.execute("SELECT username FROM usuarios WHERE TRIM(UPPER(oficina))=TRIM(UPPER(?)) AND LOWER(rol)='usuario'", (oficina,)).fetchone()
                    if existe_ofi:
                        msg=f"OFICINA REGISTRADA: La oficina {oficina} ya tiene usuario {existe_ofi['username']}. Solo 1 por oficina."
                    else:
                        db.execute("INSERT INTO usuarios (username, password, rol, oficina) VALUES (?,?,?,?)",(usuario, password, 'usuario', oficina))
                        db.commit()
                        db.close()
                        return redirect('/login?ok=registro')
            except Exception as e:
                if "UNIQUE" in str(e).upper() or "idx_oficina" in str(e).lower():
                    msg=f"OFICINA REGISTRADA: La oficina {oficina} ya está registrada"
                else:
                    msg=f"Error: {e}"
                print("ERROR REGISTRO:", e)
        # no cierres aquí todavía si hubo error
    # cierre seguro
    try:
        db.close()
    except: pass

    ops=''.join([f"<option value='{o['nombre']}'>{o['nombre']}</option>" for o in oficinas])
    return render_template_string("""
    <div style="min-height:100vh;background:#f6f3f0;display:flex;justify-content:center;align-items:center;padding:15px">
      <div style="background:white;padding:25px;border-radius:15px;box-shadow:0 4px 20px rgba(0,0,0,0.2);width:100%;max-width:420px">
        <h2 style="color:#691C32;text-align:center">Registro SEIEM</h2>
        {% if msg %}
          {% if 'OFICINA REGISTRADA' in msg %}
            <p style="background:#fff3cd;color:#856404;padding:15px;border-radius:10px;border:2px solid #ffc107;text-align:center;font-weight:bold;font-size:16px">⚠️ {{msg}}</p>
          {% else %}
            <p style="background:#ffebee;color:#b71c1c;padding:10px;border-radius:8px;text-align:center">{{msg}}</p>
          {% endif %}
        {% endif %}
        <form method="post" autocomplete="off">
          <input type="text" style="display:none">
          <input type="password" style="display:none">
          <input name="usuario_reg" required placeholder="Usuario ej: m.gonzalez" autocomplete="off" readonly onfocus="this.removeAttribute('readonly');" style="width:100%;padding:12px;border:2px solid #691C32;border-radius:8px;margin-bottom:10px">
          <input name="password_reg" type="password" required placeholder="Contraseña nueva" autocomplete="new-password" readonly onfocus="this.removeAttribute('readonly');" style="width:100%;padding:12px;border:2px solid #691C32;border-radius:8px;margin-bottom:10px">
          <input name="nombre" required placeholder="Nombre completo" autocomplete="off" style="width:100%;padding:12px;border:2px solid #691C32;border-radius:8px;margin-bottom:10px">
          <select name="oficina" required style="width:100%;padding:12px;border:2px solid #691C32;border-radius:8px;margin-bottom:15px"><option value="">-- Elige tu oficina --</option>{{ops|safe}}</select>
          <button style="width:100%;padding:13px;background:#2e7d32;color:white;border:none;border-radius:8px;font-weight:bold">REGISTRARSE</button>
        </form>
        <p style="text-align:center;margin-top:12px"><a href="/login" style="color:#691C32;font-weight:bold">← Ya tengo cuenta</a></p>
      </div>
    </div>
    """, ops=ops, msg=msg)
@app.route('/logout')
def logout(): session.clear();return redirect('/login')

# --- TODAS LAS VENTANAS QUE FALTABAN ---
@app.route('/reportes')
def reportes():
    if 'username' not in session: return redirect('/login')
    return redirect('/graficas')

@app.route('/mis_movimientos')
def mis_movimientos_alias():
    if 'username' not in session: return redirect('/login')
    return redirect('/mis_solicitudes')

@app.route('/traslados')
def traslados_alias():
    if 'username' not in session: return redirect('/login')
    return redirect('/cambio_resguardatario')

@app.route('/cambio_resguardatario', methods=['GET','POST'])
def cambio_resguardatario_view():
	if 'username' not in session: return redirect('/login')
	con=get_db(); bien=None; mensaje=""
	if request.method=='POST':
		accion=request.form.get('accion')
		if accion=='buscar':
			inv=request.form.get('no_inventario_buscar','').strip()
			bien=con.execute("SELECT * FROM bienes WHERE no_inventario=? AND (en_baja=0 OR en_baja IS NULL)",(inv,)).fetchone()
			if not bien: mensaje="❌ No se encontró el bien"
		elif accion=='solicitar_cambio':
			bien_id=request.form.get('bien_id')
			b=con.execute("SELECT * FROM bienes WHERE id=?",(bien_id,)).fetchone()
			if b:
				nuevo_resg=request.form.get('nuevo_resguardatario','').strip().upper()
				nueva_ofi=request.form.get('nueva_oficina','').strip().upper()
				motivo=request.form.get('motivo','').strip()
				if nuevo_resg and nueva_ofi:
					dup=con.execute("SELECT id FROM solicitudes WHERE no_inventario=? AND estatus='PENDIENTE' LIMIT 1",(b['no_inventario'],)).fetchone()
					if dup:
						mensaje=f"⛔ El bien {b['no_inventario']} ya tiene solicitud PENDIENTE #{dup[0]}. Espera a que el admin autorice o rechace."
						bien=b
					else:
						con.execute("INSERT INTO solicitudes (bien_id, no_inventario, descripcion, oficina_origen, oficina_destino, resguardatario_actual, resguardatario_nuevo, motivo, solicitante, oficina_solicitante, estatus, tipo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
									(b['id'], b['no_inventario'], b['descripcion'], b['oficina'], nueva_ofi, b['resguardatario'], nuevo_resg, motivo, session.get('username'), session.get('oficina'), 'PENDIENTE', 'CAMBIO RESGUARDATARIO'))
						con.commit()
						mensaje=f"✅ Solicitud enviada [{b['no_inventario']}] {b['resguardatario']} -> {nuevo_resg}"
						bien=None
	resgs=con.execute("SELECT DISTINCT resguardatario FROM bienes WHERE resguardatario!='' ORDER BY resguardatario").fetchall()
	oficinas=con.execute("SELECT nombre FROM oficinas ORDER BY nombre").fetchall()
	inventarios=con.execute("SELECT no_inventario FROM bienes WHERE (en_baja=0 OR en_baja IS NULL) ORDER BY no_inventario").fetchall()
	con.close()
	ops_resg=''.join([f"<option value='{clean(r['resguardatario'])}'>" for r in resgs])
	ops_ofi=''.join([f"<option value='{o['nombre']}'>{o['nombre']}</option>" for o in oficinas])
	ops_inv=''.join([f"<option value='{clean(r['no_inventario'])}'>" for r in inventarios])
	detalle=""
	if bien:
		detalle=f"""
		<div style="background:white;padding:20px;border-radius:12px;border:2px solid #2e7d32;margin-top:15px;">
		  <h3>✅ BIEN ENCONTRADO</h3>
		  <p><b>Inventario:</b> {clean(bien['no_inventario'])} - {clean(bien['descripcion'])}</p>
		  <p><b>Actual:</b> {clean(bien['resguardatario'])} / {clean(bien['oficina'])}</p>
		  <form method="post" style="background:#f9f9f9;padding:15px;border-radius:8px;margin-top:15px;border:1px solid #ddd">
			<input type="hidden" name="accion" value="solicitar_cambio"><input type="hidden" name="bien_id" value="{bien['id']}">
			<h4 style="color:#691C32">Solicitar cambio a:</h4>
			<label>Nuevo resguardatario *</label><br><input list="list_resg" name="nuevo_resguardatario" required style="width:100%;padding:12px"><br><br>
			<label>Nueva oficina *</label><br><select name="nueva_oficina" required style="width:100%;padding:12px"><option value="">-- Elige --</option>{ops_ofi}</select><br><br>
			<label>Motivo</label><br><textarea name="motivo" style="width:100%"></textarea><br><br>
			<button style="width:100%;padding:13px;background:#691C32;color:white;border:none;border-radius:8px;font-weight:bold">ENVIAR SOLICITUD PENDIENTE</button>
		  </form>
		</div>
		"""
	return render_page(f"""
	<div style="max-width:900px;margin:auto">
	  <div style="background:white;padding:20px;border-radius:12px">
		<h2 style="color:#691C32">CAMBIO DE RESGUARDATARIO</h2>
		<form method="post" style="display:flex;gap:8px;margin-top:12px">
		  <input type="hidden" name="accion" value="buscar">
		  <input list="list_inv_cambio" name="no_inventario_buscar" required placeholder="Escribe o selecciona No. Inventario" style="flex:1;padding:12px;border:2px solid #691C32;border-radius:8px">
		  <button style="background:#691C32;color:white;border:none;padding:12px 20px;border-radius:8px;font-weight:bold">BUSCAR DATOS</button>
		</form>
		{'<p style="color:'+('green' if '✅' in mensaje else 'red')+';font-weight:bold;margin-top:10px">'+mensaje+'</p>' if mensaje else ''}
	  </div>
	  <datalist id="list_resg">{ops_resg}</datalist>
	  <datalist id="list_inv_cambio">{ops_inv}</datalist>
	  {detalle}
	</div>
	""")
@app.route('/dashboard', methods=['GET','POST'])
@solo_admin
def dashboard():
    if 'username' not in session:
        return redirect('/login')
    db = get_db()
    mensaje = ""
    msg_masivo = ""
    filtro_resg = ""

    def clean(v):
        if v is None: return ""
        s=str(v).strip()
        if s.lower() in ["nan","none",""]: return ""
        return s

    # --- 1. CARGAR PADRON EXCEL ---
    if request.method == 'POST' and 'archivo_excel' in request.files:
        file = request.files.get('archivo_excel')
        if file and file.filename.endswith(('.xlsx','.xls','.XLSX')):
            import pandas as pd, os
            os.makedirs('uploads', exist_ok=True)
            ruta = os.path.join('uploads', file.filename)
            file.save(ruta)
            df = pd.read_excel(ruta)
            df.columns = [str(c).strip().upper() for c in df.columns]
            db.execute("DELETE FROM bienes")
            count = 0
            for _, r in df.iterrows():
                inv = str(r.get('INVENTARIO','') or (r.iloc[0] if len(r)>0 else "")).strip()
                bien = str(r.get('NOMBRE ARTÍCULO','') or r.get('NOMBRE ARTICULO','') or (r.iloc[1] if len(r)>1 else "")).strip()
                marca = str(r.get('MARCA','') or (r.iloc[2] if len(r)>2 else "")).strip()
                modelo = str(r.get('MODELO','') or (r.iloc[3] if len(r)>3 else "")).strip()
                serie = str(r.get('SERIE','') or (r.iloc[4] if len(r)>4 else "")).strip()
                resg = str(r.get('NOMBRE DEL RESGUARDATARIO','') or (r.iloc[5] if len(r)>5 else "")).strip()
                if inv=="" and bien=="" and resg=="":
                    continue
                db.execute("INSERT INTO bienes (no_inventario, descripcion, marca, modelo, serie, oficina, resguardatario) VALUES (?,?,?,?,?,?,?)",
                           (inv, bien, marca, modelo, serie, "", resg))
                count+=1
            db.commit()
            mensaje = f"<div style='background:#E8F5E9;padding:12px;border-radius:8px;color:#2E7D32;margin-bottom:15px;font-weight:bold'>✅ Padrón cargado: {count} bienes</div>"
        else:
            mensaje = "<div style='background:#FFEBEE;padding:12px;border-radius:8px;color:#C62828;margin-bottom:15px'>❌ Sube un Excel.xlsx válido</div>"

    # --- 2. MOVIMIENTO MASIVO ---
    if request.method == 'POST':
        accion=request.form.get('accion')
        if accion=='asignar_oficina_masiva' and session.get('rol')=='admin':
            resg_sel=request.form.get('resguardatario_masivo','').strip()
            ofi_nueva=request.form.get('oficina_nueva','').strip()
            if resg_sel and ofi_nueva:
                total_afect=db.execute("SELECT COUNT(*) as c FROM bienes WHERE resguardatario=? AND (en_baja=0 OR en_baja IS NULL)",(resg_sel,)).fetchone()['c']
                db.execute("UPDATE bienes SET oficina=? WHERE resguardatario=?",(ofi_nueva, resg_sel))
                db.commit()
                msg_masivo=f"✅ Se asignó oficina {ofi_nueva} a {total_afect} bienes de {resg_sel}"
                filtro_resg=resg_sel
        if request.form.get('resguardatario_masivo'):
            filtro_resg=request.form.get('resguardatario_masivo','').strip()

    if not filtro_resg:
        filtro_resg=request.args.get('resguardatario','').strip()

    # --- TOTAL REAL ---
    total=db.execute("SELECT COUNT(*) as c FROM bienes").fetchone()['c']
    resguardatarios_lista=db.execute("SELECT DISTINCT resguardatario FROM bienes WHERE resguardatario!='' ORDER BY resguardatario").fetchall()
    oficinas_lista=db.execute("SELECT nombre FROM oficinas ORDER BY nombre").fetchall()

    if filtro_resg:
        bienes=db.execute("SELECT * FROM bienes WHERE resguardatario=? AND (en_baja=0 OR en_baja IS NULL) ORDER BY id DESC",(filtro_resg,)).fetchall()
        titulo=f"BIENES DE: {filtro_resg} - {len(bienes)} bienes"
    else:
        bienes=db.execute("SELECT * FROM bienes WHERE (en_baja=0 OR en_baja IS NULL) ORDER BY id DESC LIMIT 2000").fetchall()
        titulo=f"PADRON ACTUAL {total} - Total resguardatarios: {len(resguardatarios_lista)}"

    ops_resg=''.join([f"<option value='{clean(r['resguardatario'])}' {'selected' if clean(r['resguardatario'])==filtro_resg else ''}>{clean(r['resguardatario'])}</option>" for r in resguardatarios_lista])
    ops_ofi=''.join([f"<option value='{o['nombre']}'>{o['nombre']}</option>" for o in oficinas_lista])

    panel_masivo=f"""
        <div style="background:#e8f5e9;border:2px solid #4caf50;border-radius:12px;padding:15px;margin-bottom:15px">
          <h3 style="color:#2e7d32;margin-bottom:8px">⚡ MOVIMIENTO MASIVO POR RESGUARDATARIO (Solo Admin)</h3>
          <form method="post" style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:end">
            <div style="flex:2;min-width:280px"><label style="font-size:11px;font-weight:bold">Resguardatario</label><br>
            <input list="lista_resg_dashboard" name="resguardatario_masivo" value="{filtro_resg}" placeholder="Ej: JUAN..." style="width:100%;padding:10px;border:2px solid #2e7d32;border-radius:6px">
            <datalist id="lista_resg_dashboard">{ops_resg}</datalist></div>
            <button name="accion" value="filtrar" style="background:#555;color:white;border:none;padding:11px 15px;border-radius:6px;font-weight:bold">🔍 FILTRAR</button>
            <div style="flex:1;min-width:220px"><label style="font-size:11px;font-weight:bold">Asignar a Oficina</label><br><select name="oficina_nueva" style="width:100%;padding:10px;border:2px solid #2e7d32;border-radius:6px"><option value="">-- Elige Oficina --</option>{ops_ofi}</select></div>
            <button name="accion" value="asignar_oficina_masiva" style="background:#2e7d32;color:white;border:none;padding:11px 20px;border-radius:6px;font-weight:bold">ASIGNAR A TODOS</button>
            <a href="/dashboard" style="background:#ccc;color:#333;padding:11px 15px;border-radius:6px;text-decoration:none;font-weight:bold">VER TODOS</a>
          </form>
          {'<p style="color:green;font-weight:bold;margin-top:8px">'+msg_masivo+'</p>' if msg_masivo else ''}
        </div>
        """
    filas="".join([f"<tr><td style='border:1px solid #eee;padding:4px;font-size:11px'>{clean(r['no_inventario'])}</td><td style='border:1px solid #eee;padding:4px;font-size:11px'>{clean(r['descripcion'])}</td><td style='border:1px solid #eee;padding:4px;font-size:11px'>{clean(r['marca'])}</td><td style='border:1px solid #eee;padding:4px;font-size:11px'>{clean(r['modelo'])}</td><td style='border:1px solid #eee;padding:4px;font-size:11px'>{clean(r['serie'])}</td><td style='border:1px solid #eee;padding:4px;font-size:11px;background:{'#ffcdd2' if not clean(r['oficina']) else '#e8f5e9'}'>{clean(r['oficina']) or 'SIN OFICINA'}</td><td style='border:1px solid #eee;padding:4px;font-size:11px'>{clean(r['resguardatario'])}</td></tr>" for r in bienes])

    return render_page(f"""
    <div style="max-width:1100px;margin:auto">
     <div style="background:white;padding:20px;border-radius:12px;margin-bottom:15px;border:2px solid #691C32">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h2 style="color:#691C32;margin:0">CARGAR PADRON EXCEL - SEIEM</h2>
        <button onclick="document.getElementById('modalNuevo').style.display='block'" style="background:#691C32;color:white;border:none;padding:10px 18px;border-radius:6px;font-weight:bold;cursor:pointer;">+ NUEVO BIEN</button>
      </div>

    <div id="modalNuevo" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:9999;">
      <div style="background:white; width:90%; max-width:500px; margin:50px auto; padding:20px; border-radius:10px; max-height:90vh; overflow:auto;">
        <h3 style="color:#691C32; margin-top:0;">ALTA DE BIEN NUEVO</h3>
        <form method="POST" action="/agregar_bien">
          <label style="font-weight:bold;">No. Inventario *</label><input type="text" name="no_inventario" required style="width:100%;padding:8px;margin-bottom:8px;border:1px solid #ccc;border-radius:4px;">
          <label style="font-weight:bold;">Nombre del Bien *</label><input type="text" name="descripcion" required placeholder="Ej. LAPTOP, SILLA" style="width:100%;padding:8px;margin-bottom:8px;border:1px solid #ccc;border-radius:4px;">
          <label style="font-weight:bold;">Marca</label><input type="text" name="marca" style="width:100%;padding:8px;margin-bottom:8px;border:1px solid #ccc;border-radius:4px;">
          <label style="font-weight:bold;">Modelo</label><input type="text" name="modelo" style="width:100%;padding:8px;margin-bottom:8px;border:1px solid #ccc;border-radius:4px;">
          <label style="font-weight:bold;">Serie</label><input type="text" name="serie" style="width:100%;padding:8px;margin-bottom:8px;border:1px solid #ccc;border-radius:4px;">
          <label style="font-weight:bold;">Oficina</label><select name="oficina" style="width:100%;padding:8px;margin-bottom:8px;"><option value="Recursos Materiales y Financieros">Recursos Materiales y Financieros</option>{ops_ofi}</select>
          <label style="font-weight:bold;">Resguardatario *</label><input type="text" name="resguardatario" required list="lista_resg_dashboard" value="{filtro_resg}" style="width:100%;padding:8px;margin-bottom:12px;border:1px solid #ccc;border-radius:4px;">
          <div style="display:flex;gap:10px;">
            <button type="submit" style="flex:1;background:#2E7D32;color:white;border:none;padding:10px;border-radius:5px;font-weight:bold;">GUARDAR BIEN</button>
            <button type="button" onclick="document.getElementById('modalNuevo').style.display='none'" style="flex:1;background:#ccc;border:none;padding:10px;border-radius:5px;">CANCELAR</button>
          </div>
        </form>
      </div>
    </div>
                {mensaje}
                <form method="POST" enctype="multipart/form-data" style="background:#FFF8E1;padding:15px;border-radius:10px;border:2px dashed #FF9800;text-align:center;margin-top:10px">
                    <input type="file" name="archivo_excel" accept=".xlsx,.xls" required style="padding:10px;background:white;border-radius:5px">
                    <button style="background:#691C32;color:white;padding:12px 25px;border:none;border-radius:8px;font-weight:bold;cursor:pointer;margin-left:10px">CARGAR PADRON</button>
                </form>
                <div style="margin-top:10px;background:#F3E5F5;padding:10px;border-radius:6px"><b>Padrón actual:</b> {total} bienes cargados</div>
            </div>
            {panel_masivo}
            <h2>{titulo}</h2>
            <div style='background:white;padding:10px;overflow:auto;border-radius:10px'><table style='width:100%;border-collapse:collapse'><tr style='background:#691C32;color:white'><th>Inv</th><th>Bien</th><th>Marca</th><th>Modelo</th><th>Serie</th><th>Oficina</th><th>Resguardatario</th></tr>{filas}</table></div>
        </div>
        """)
@app.route('/graficas')
def graficas():
    if 'username' not in session: return redirect('/login')
    import json
    rol=session.get('rol'); oficina_user=session.get('oficina')
    oficina_f=request.args.get('oficina','').strip()
    resg_f=request.args.get('resguardatario','').strip()
    if rol!='admin': oficina_f=oficina_user
    db=get_db()
    where=" WHERE (en_baja=0 OR en_baja IS NULL) "; params=[]
    if oficina_f: where+=" AND oficina LIKE? "; params.append(f"%{oficina_f}%")
    if resg_f: where+=" AND resguardatario LIKE? "; params.append(f"%{resg_f}%")
    total=db.execute(f"SELECT COUNT(*) as c FROM bienes {where}", params).fetchone()['c']
    por_resg=db.execute(f"SELECT resguardatario, COUNT(*) as cant FROM bienes {where} GROUP BY resguardatario ORDER BY cant DESC LIMIT 10", params).fetchall()
    por_ofi=db.execute(f"SELECT oficina, COUNT(*) as cant FROM bienes {where} GROUP BY oficina ORDER BY cant DESC LIMIT 10", params).fetchall()
    if rol=='admin':
        oficinas=db.execute("SELECT DISTINCT oficina FROM bienes WHERE oficina!='' ORDER BY oficina").fetchall()
        resguardatarios=db.execute("SELECT DISTINCT resguardatario FROM bienes WHERE resguardatario!='' ORDER BY resguardatario").fetchall()
    else:
        oficinas=[{'oficina':oficina_user}]
        resguardatarios=db.execute("SELECT DISTINCT resguardatario FROM bienes WHERE oficina=? ORDER BY resguardatario",(oficina_user,)).fetchall()
    db.close()
    ops_ofi=''.join([f"<option value='{o['oficina']}' {'selected' if oficina_f==o['oficina'] else ''}>{clean(o['oficina'])}</option>" for o in oficinas])
    ops_resg=''.join([f"<option value='{r['resguardatario']}' {'selected' if resg_f==r['resguardatario'] else ''}>{clean(r['resguardatario'])}</option>" for r in resguardatarios])
    return render_page(f"""
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <div style="background:white;padding:15px;border-radius:12px;margin-bottom:15px">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px">
        <h2 style="color:#691C32">REPORTES - Total {total}</h2>
        <div style="display:flex;gap:8px">
          <a href="/reporte_pdf?oficina={oficina_f}&resguardatario={resg_f}" target="_blank" style="background:#212121;color:white;padding:8px 12px;border-radius:6px;text-decoration:none;font-size:12px">PDF</a>
          <a href="/reporte_excel?oficina={oficina_f}&resguardatario={resg_f}" style="background:#2e7d32;color:white;padding:8px 12px;border-radius:6px;text-decoration:none;font-size:12px">EXCEL</a>
        </div>
      </div>
      <form method="GET" style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <select name="oficina" style="flex:1;padding:10px;border-radius:8px;border:2px solid #691C32" {'disabled' if rol!='admin' else ''}><option value="">-- TODAS --</option>{ops_ofi}</select>
        <select name="resguardatario" style="flex:1;padding:10px;border-radius:8px;border:2px solid #691C32"><option value="">-- TODOS --</option>{ops_resg}</select>
        <button style="background:#691C32;color:white;border:none;padding:10px 18px;border-radius:8px">FILTRAR</button>
        <a href="/graficas" style="background:#ddd;padding:10px 15px;border-radius:8px;text-decoration:none;color:black">LIMPIAR</a>
      </form>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px">
      <div style="background:white;padding:15px;border-radius:12px"><h4>Top 10 Por Resguardatario</h4><canvas id="cResg"></canvas></div>
      <div style="background:white;padding:15px;border-radius:12px"><h4>Por Oficina</h4><canvas id="cOfi"></canvas></div>
    </div>
    <script>
      new Chart(document.getElementById('cResg'),{{type:'bar',data:{{labels:{json.dumps([clean(r['resguardatario'])[:20] for r in por_resg])},datasets:[{{label:'Bienes',data:{json.dumps([r['cant'] for r in por_resg])},backgroundColor:'#691C32'}}]}}}})
      new Chart(document.getElementById('cOfi'),{{type:'bar',data:{{labels:{json.dumps([clean(r['oficina'])[:20] for r in por_ofi])},datasets:[{{label:'Bienes',data:{json.dumps([r['cant'] for r in por_ofi])},backgroundColor:'#C9A86A'}}]}}}})
    </script>
    """)

@app.route('/reporte_pdf')
def reporte_pdf():
    from flask import send_file
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from xml.sax.saxutils import escape
    import io, datetime
    from collections import defaultdict

    oficina = request.args.get('oficina','').strip()
    resguardatario_q = request.args.get('resguardatario','').strip()

    db = get_db()
    if resguardatario_q and resguardatario_q.upper() != "TODOS":
        bienes = db.execute("SELECT * FROM bienes WHERE oficina=? AND resguardatario=? ORDER BY resguardatario", (oficina, resguardatario_q)).fetchall()
    else:
        bienes = db.execute("SELECT * FROM bienes WHERE oficina=? ORDER BY resguardatario", (oficina,)).fetchall()
        resguardatario_q = ""
    db.close()

    def limpia(v):
        if v is None: return ""
        s=str(v).strip()
        if s.lower() in ["nan","none","nat","null",""]: return ""
        return s

    # --- ESTILOS QUE SE AUTO-AJUSTAN ---
    style_head = ParagraphStyle('head', fontName='Helvetica-Bold', fontSize=6, leading=7, alignment=TA_CENTER, textColor=colors.white)
    style_cell = ParagraphStyle('cell', fontName='Helvetica', fontSize=6.5, leading=7.5, alignment=TA_CENTER, wordWrap='CJK')
    style_cell_small = ParagraphStyle('cell_small', fontName='Helvetica', fontSize=5, leading=5.5, alignment=TA_CENTER, wordWrap='CJK')
    style_desc = ParagraphStyle('desc', fontName='Helvetica', fontSize=6, leading=6.5, alignment=TA_LEFT, wordWrap='CJK')

    def Celda(texto, es_header=False, es_desc=False):
        t = escape(limpia(texto))
        if not t: return Paragraph("", style_cell)
        if es_header:
            return Paragraph(t, style_head)
        # Si es muy largo, usa estilo mas chico y que lo parta
        if len(t) > 30 or es_desc:
            return Paragraph(t, style_desc if es_desc else style_cell_small)
        if len(t) > 18:
            return Paragraph(t, style_cell_small)
        return Paragraph(t, style_cell)

    from reportlab.pdfgen import canvas
    from xml.sax.saxutils import escape

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter

    # Encabezado
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#691C32"))
    c.drawCentredString(w/2, h-60, "SERVICIOS EDUCATIVOS INTEGRADOS AL ESTADO DE MEXICO")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    c.drawString(80, h-80, f"REPORTE DE BIENES - {limpia(oficina)}")
    c.drawString(80, h-95, f"FECHA: {datetime.date.today().strftime('%d/%m/%Y')}  TOTAL: {len(bienes)} bienes")
    c.drawString(80, h-110, f"OFICINA: {limpia(oficina)}")
    y = h-125
    if resguardatario_q:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(80, y, f"RESGUARDATARIO: {limpia(resguardatario_q)}")
        y -= 15

    grupos = defaultdict(list)
    for b in bienes:
        grupos[limpia(b["resguardatario"])].append(b)

    y -= 10
    for nombre_resguardo, lista in grupos.items():
        if y < 150:
            c.showPage()
            y = h-60
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(colors.HexColor("#691C32"))
        c.drawString(40, y, f"RESGUARDATARIO: {nombre_resguardo} - {len(lista)} bienes")
        y -= 12

        data = [[Celda("INVENTARIO",True), Celda("BIEN / DESCRIPCION",True), Celda("MARCA",True), Celda("MODELO",True), Celda("SERIE",True)]]
        for b in lista:
            k=b.keys()
            inv=limpia(b["inventario"] if "inventario" in k else b["no_inventario"] if "no_inventario" in k else "")
            desc=limpia(b["descripcion"] if "descripcion" in k else b["nombre"] if "nombre" in k else "")
            marca=limpia(b["marca"])
            modelo=limpia(b["modelo"])
            serie=limpia(b["serie"])
            data.append([Celda(inv), Celda(desc, es_desc=True), Celda(marca), Celda(modelo), Celda(serie)])

        # Columna SERIE mas ancha para que no se corte
        table = Table(data, colWidths=[55, 170, 55, 55, 115], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#691C32")),
            ('BACKGROUND', (0,1), (-1,-1), colors.white),
            ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor("#aaa")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        tw, th = table.wrap(0,0)
        if y - th < 40:
            c.showPage()
            y = h-60
        table.drawOn(c, 40, y-th)
        y = y-th-20

    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=False, mimetype='application/pdf')
@app.route('/reporte_excel')
def reporte_excel():
    oficina=request.args.get('oficina',''); resg=request.args.get('resguardatario','')
    con=get_db(); q="SELECT no_inventario as INVENTARIO, descripcion as BIEN, marca as MARCA, modelo as MODELO, serie as SERIE, resguardatario as RESGUARDATARIO, oficina as OFICINA FROM bienes WHERE 1=1"; p=[]
    if oficina: q+=" AND oficina LIKE?"; p.append(f"%{oficina}%")
    if resg: q+=" AND resguardatario LIKE?"; p.append(f"%{resg}%")
    if session.get('rol')!='admin': q+=" AND oficina=?"; p.append(session.get('oficina'))
    df=pd.read_sql_query(q, con, params=p); con.close()
    out=io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer: df.to_excel(writer, index=False)
    out.seek(0); return send_file(out, download_name=f"Reporte_{oficina}.xlsx", as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/resguardos')
def lista_resguardos():
    if 'username' not in session: return redirect('/login')
    rol=session.get('rol'); ofi_u=session.get('oficina'); con=get_db()
    
    oficina_sel = request.args.get('oficina','').strip()
    
    if rol=='admin': 
        oficinas=con.execute("SELECT nombre FROM oficinas ORDER BY nombre").fetchall()
        if oficina_sel:
            rows=con.execute("SELECT resguardatario, oficina, COUNT(*) as total FROM bienes WHERE oficina=? AND resguardatario!='' GROUP BY resguardatario, oficina ORDER BY resguardatario",(oficina_sel,)).fetchall()
        else:
            rows=con.execute("SELECT resguardatario, oficina, COUNT(*) as total FROM bienes WHERE resguardatario!='' GROUP BY resguardatario, oficina ORDER BY oficina, resguardatario").fetchall()
    else: 
        oficina_sel = ofi_u
        oficinas=[]
        rows=con.execute("SELECT resguardatario, oficina, COUNT(*) as total FROM bienes WHERE oficina=? AND resguardatario!='' GROUP BY resguardatario ORDER BY resguardatario",(ofi_u,)).fetchall()
    con.close()
    
    filas="".join([f"<tr><td style='border:1px solid #eee;padding:7px;font-size:13px'>{clean(r['resguardatario'])}</td><td style='border:1px solid #eee;padding:7px;font-size:12px'>{clean(r['oficina'])}</td><td style='border:1px solid #eee;padding:7px;text-align:center;font-weight:bold'>{r['total']}</td><td style='border:1px solid #eee;padding:7px;text-align:center'><a href='/tarjeta/{r['resguardatario']}' target='_blank' style='background:#691C32;color:white;padding:6px 12px;text-decoration:none;border-radius:6px;font-size:11px;font-weight:bold'>📄 PDF</a></td></tr>" for r in rows])
    
    # Opciones del dropdown
    ops = "".join([f"<option value='{o['nombre']}' {'selected' if oficina_sel==o['nombre'] else ''}>{o['nombre']}</option>" for o in oficinas])
    
    # Panel bonito solo para admin
    panel_admin = ""
    if rol=='admin':
        panel_admin = f"""
        <div style="background:linear-gradient(135deg,#e8f5e9 0%,#c8e6c9 100%);border:2px solid #2e7d32;border-radius:12px;padding:18px;margin-bottom:18px;box-shadow:0 2px 8px rgba(0,0,0,0.1)">
          <h3 style="margin:0 0 12px 0;color:#2e7d32;font-size:16px">🖨️ Generar Resguardos por Oficina</h3>
          <form method="GET" action="/resguardos" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
            <div style="flex:1;min-width:280px">
              <label style="font-size:11px;font-weight:bold;color:#2e7d32">SELECCIONA LA OFICINA</label><br>
              <select name="oficina" style="width:100%;padding:12px;border:2px solid #2e7d32;border-radius:8px;font-size:13px;font-weight:bold;background:white">
                <option value="">-- TODAS LAS OFICINAS ({len(oficinas)}) --</option>
                {ops}
              </select>
            </div>
            <button type="submit" style="background:#555;color:white;border:none;padding:12px 20px;border-radius:8px;font-weight:bold;cursor:pointer">🔍 FILTRAR</button>
            <a href="/resguardos" style="background:#ddd;color:#333;padding:12px 18px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:12px">LIMPIAR</a>
          </form>
          
          <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap">
            <a href="/tarjetas_todas" target="_blank" style="flex:1;min-width:200px;background:#000;color:white;padding:12px;text-align:center;text-decoration:none;border-radius:8px;font-weight:bold;font-size:13px">🖨️ PDF TODOS JUNTOS ({len(rows)} resguardatarios)</a>
            {'<a href="/tarjeta_oficina/'+oficina_sel+'" target="_blank" style="flex:1;min-width:200px;background:#2e7d32;color:white;padding:12px;text-align:center;text-decoration:none;border-radius:8px;font-weight:bold;font-size:13px;box-shadow:0 3px 10px rgba(46,125,50,0.3)">📄 GENERAR PDF DE: '+oficina_sel+'</a>' if oficina_sel else '<span style="flex:1;min-width:200px;background:#aaa;color:white;padding:12px;text-align:center;border-radius:8px;font-size:12px">Selecciona una oficina para generar su PDF</span>'}
          </div>
        </div>
        """
    else:
        panel_admin = f"""
        <div style="background:#e8f5e9;border:2px solid #2e7d32;border-radius:12px;padding:15px;margin-bottom:15px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
          <div><b style="color:#2e7d32">Oficina: {ofi_u} - {len(rows)} resguardatarios</b></div>
          <a href="/tarjeta_oficina/{ofi_u}" target="_blank" style="background:#2e7d32;color:white;padding:10px 20px;text-decoration:none;border-radius:8px;font-weight:bold">📄 GENERAR PDF DE MI OFICINA</a>
        </div>
        """
    
    return render_page(f"""
    <div style='background:white;padding:20px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08)'>
      <div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:10px'>
        <h2 style='margin:0;color:#691C32'>Resguardos - {len(rows)} resguardatarios {'- '+oficina_sel if oficina_sel else ''}</h2>
      </div>
      
      {panel_admin}
      
      <div style='overflow:auto;max-height:70vh;border:1px solid #eee;border-radius:8px'>
        <table style='width:100%;border-collapse:collapse'>
          <thead style='position:sticky;top:0;z-index:1'><tr style='background:#691C32;color:white'><th style='padding:10px;text-align:left;font-size:12px'>Resguardatario</th><th style='padding:10px;text-align:left;font-size:12px'>Oficina</th><th style='padding:10px;font-size:12px'>Total Bienes</th><th style='padding:10px;font-size:12px'>Acción</th></tr></thead>
          <tbody>{filas if filas else '<tr><td colspan=4 style="padding:20px;text-align:center;color:#999">No hay resguardatarios</td></tr>'}</tbody>
        </table>
      </div>
    </div>
    """)

@app.route('/traslados', methods=['GET','POST'])
def traslados():
    if 'username' not in session: return redirect('/login')
    con=get_db(); bien=None; mensaje=""
    if request.method=='POST':
        accion=request.form.get('accion')
        if accion=='buscar':
            inv=request.form.get('no_inventario_buscar','').strip()
            bien=con.execute("SELECT * FROM bienes WHERE no_inventario=? AND (en_baja=0 OR en_baja IS NULL)",(inv,)).fetchone()
            if not bien: mensaje="No se encontró el bien"
        elif accion=='solicitar_cambio':
            bien_id=request.form.get('bien_id')
            b=con.execute("SELECT * FROM bienes WHERE id=?",(bien_id,)).fetchone()
            if b:
                nuevo_resg=request.form.get('nuevo_resguardatario','').strip().upper()
                nueva_ofi=request.form.get('nueva_oficina','').strip()
                motivo=request.form.get('motivo','').strip()
                if nuevo_resg and nueva_ofi:
                    no_inv_bloqueo = b['no_inventario']
                    dup = con.execute("SELECT id FROM solicitudes WHERE no_inventario=? AND estatus='PENDIENTE' LIMIT 1", (no_inv_bloqueo,)).fetchone()
                    if dup:
                        mensaje=f"NO SE PUEDE. El inventario {no_inv_bloqueo} ya tiene solicitud PENDIENTE #{dup[0]}. Debe ser autorizada o rechazada por el admin."
                        bien=b
                    else:
                        con.execute("INSERT INTO solicitudes (bien_id, no_inventario, descripcion, oficina_origen, oficina_destino, resguardatario_actual, resguardatario_nuevo, motivo, solicitante, oficina_solicitante, estatus) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                    (b['id'], b['no_inventario'], b['descripcion'], b['oficina'], nueva_ofi, b['resguardatario'], nuevo_resg, motivo, session['username'], session.get('oficina',''), 'PENDIENTE'))
                        con.commit()
                        mensaje=f"Solicitud enviada: {b['no_inventario']} {b['resguardatario']} -> {nuevo_resg}"
                        bien=None
    resgs=con.execute("SELECT DISTINCT resguardatario FROM bienes WHERE resguardatario!='' ORDER BY resguardatario").fetchall()
    oficinas=con.execute("SELECT nombre FROM oficinas ORDER BY nombre").fetchall()
    inventarios=con.execute("SELECT no_inventario FROM bienes WHERE (en_baja=0 OR en_baja IS NULL) ORDER BY no_inventario").fetchall()
    con.close()
    ops_resg=''.join([f"<option value='{clean(r['resguardatario'])}'>{clean(r['resguardatario'])}</option>" for r in resgs])
    ops_ofi=''.join([f"<option value='{o['nombre']}'>{o['nombre']}</option>" for o in oficinas])
    ops_inv=''.join([f"<option value='{clean(r['no_inventario'])}'>{clean(r['no_inventario'])}</option>" for r in inventarios])
    detalle=""
    if bien:
        detalle=f"""
        <div style="background:#e8f5e9;padding:20px;border-radius:12px;border:2px solid #2e7d32;margin-top:15px">
          <h3>Bien encontrado</h3>
          <p><b>Inventario:</b> {clean(bien['no_inventario'])} - {clean(bien['descripcion'])}<br><b>Actual:</b> {clean(bien['resguardatario'])} - {clean(bien['oficina'])}</p>
          <form method="post" style="background:white;padding:15px;border-radius:8px">
            <input type="hidden" name="accion" value="solicitar_cambio"><input type="hidden" name="bien_id" value="{bien['id']}">
            <label>Nuevo resguardatario</label><br><input list="list_resg" name="nuevo_resguardatario" required style="width:100%;padding:12px"><br><br>
            <label>Nueva oficina</label><br><select name="nueva_oficina" required style="width:100%;padding:12px"><option value="">-- Elige --</option>{ops_ofi}</select><br><br>
            <label>Motivo</label><br><textarea name="motivo" style="width:100%"></textarea><br><br>
            <button style="width:100%;padding:13px;background:#691C32;color:white;border:none;border-radius:8px;font-weight:bold">ENVIAR SOLICITUD</button>
          </form>
        </div>
        """
    return render_page(f"""
    <div style="max-width:900px;margin:auto">
      <div style="background:white;padding:20px;border-radius:12px">
        <h2 style="color:#691C32">TRASLADOS / CAMBIO DE RESGUARDATARIO</h2>
        <form method="post" style="display:flex;gap:8px;margin-top:12px">
          <input type="hidden" name="accion" value="buscar">
          <input list="list_inv" name="no_inventario_buscar" required placeholder="No. Inventario" style="flex:1;padding:12px;border:2px solid #691C32;border-radius:8px">
          <button style="background:#691C32;color:white;border:none;padding:12px 20px;border-radius:8px;font-weight:bold">BUSCAR</button>
        </form>
        {'<p style="color:green;font-weight:bold">'+mensaje+'</p>' if mensaje else ''}
      </div>
      <datalist id="list_resg">{ops_resg}</datalist>
      <datalist id="list_inv">{ops_inv}</datalist>
      {detalle}
    </div>
    """)
@app.route('/oficios/<path:filename>')
def descargar_oficio(filename):
    from flask import send_from_directory
    import os
    carpeta = os.path.join(os.getcwd(), 'oficios')
    if not os.path.exists(carpeta):
        carpeta = os.path.join(os.getcwd(), 'inventario-seiem', 'oficios')
    return send_from_directory(carpeta, filename, as_attachment=True)

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/mis_solicitudes', methods=['GET','POST'])
def mis_solicitudes():
    if 'username' not in session: return redirect('/login')
    db=get_db()
    usuario = session['username']

    # Parche por si faltan columnas
    for col in ["ALTER TABLE solicitudes ADD COLUMN oficina_solicitante TEXT",
                "ALTER TABLE solicitudes ADD COLUMN solicitante TEXT",
                "ALTER TABLE solicitudes ADD COLUMN estatus TEXT",
                "ALTER TABLE solicitudes ADD COLUMN tipo TEXT",
                "ALTER TABLE solicitudes ADD COLUMN estado TEXT",
                "ALTER TABLE solicitudes ADD COLUMN observaciones_admin TEXT"]:
        try:
            db.execute(col)
            db.commit()
        except:
            pass
    oficina_row = db.execute("SELECT oficina, rol FROM usuarios WHERE username=?",(usuario,)).fetchone()
    oficina_user = oficina_row['oficina'] if oficina_row else ''
    rol_db = str(oficina_row['rol']).lower() if oficina_row and oficina_row['rol'] else 'user'
    es_admin = usuario.lower() in ['admin','aida'] or rol_db == 'admin'

    if request.method=='POST' and es_admin:
        id_sol=request.form.get('id_solicitud')
        obs_admin=request.form.get('observaciones_admin','')
        accion=request.form.get('accion')
        if id_sol:
            sol=db.execute("SELECT * FROM solicitudes WHERE id=?",(id_sol,)).fetchone()
            if sol:
                if accion=='aprobar':
                    # Hace el cambio real en bienes
                    db.execute("UPDATE bienes SET resguardatario=?, oficina=? WHERE id=?",
                               (sol['resguardatario_nuevo'], sol['oficina_destino'], sol['bien_id']))
                    db.execute("UPDATE solicitudes SET estatus='APROBADO', estado='APROBADO', observaciones_admin=? WHERE id=?",
                               (obs_admin or 'Aprobado por admin', id_sol))
                elif accion=='rechazar':
                    try:
                        db.execute("UPDATE solicitudes SET estatus='RECHAZADO', estado='RECHAZADO', observaciones_admin=? WHERE id=?",
                                   (obs_admin or 'Rechazado', id_sol))
                    except:
                        # Si no existe la columna, la crea
                        try:
                            db.execute("ALTER TABLE solicitudes ADD COLUMN observaciones_admin TEXT")
                            db.commit()
                        except:
                            pass
                        # Intenta guardar de nuevo con motivo
                        try:
                            db.execute("UPDATE solicitudes SET estatus='RECHAZADO', estado='RECHAZADO', observaciones_admin=? WHERE id=?",
                                       (obs_admin or 'Rechazado', id_sol))
                        except:
                            db.execute("UPDATE solicitudes SET estatus='RECHAZADO', estado='RECHAZADO' WHERE id=?", (id_sol,))
                db.commit()
    # --- CONSULTAS CORREGIDAS ---
    if es_admin:
        pendientes=db.execute("SELECT * FROM solicitudes WHERE estatus='PENDIENTE' OR estado='PENDIENTE' ORDER BY id DESC").fetchall()
        historial=db.execute("SELECT * FROM solicitudes WHERE estatus!='PENDIENTE' AND estado!='PENDIENTE' ORDER BY id DESC LIMIT 200").fetchall()
        pendientes_bp=db.execute("SELECT * FROM bienes_propios WHERE estatus='PENDIENTE' ORDER BY id DESC").fetchall()
        historial_bp=db.execute("SELECT * FROM bienes_propios WHERE estatus!='PENDIENTE' ORDER BY id DESC LIMIT 200").fetchall()
    else:
        # PARA USUARIO NORMAL - AHORA SI LLENA PENDIENTES
        pendientes=db.execute("SELECT * FROM solicitudes WHERE (solicitante=? OR oficina_solicitante=?) AND (estatus='PENDIENTE' OR estado='PENDIENTE') ORDER BY id DESC",
                              (usuario, oficina_user)).fetchall()
        historial=db.execute("SELECT * FROM solicitudes WHERE (solicitante=? OR oficina_solicitante=?) AND (estatus!='PENDIENTE' AND estado!='PENDIENTE') ORDER BY id DESC",
                             (usuario, oficina_user)).fetchall()
        
        historial_temp=db.execute("SELECT * FROM bienes_propios WHERE usuario_solicita=? OR usuario_solicitante=? ORDER BY id DESC",(usuario, usuario)).fetchall()
        pendientes_bp=[s for s in historial_temp if s['estatus']=='PENDIENTE']
        historial_bp=[s for s in historial_temp if s['estatus']!='PENDIENTE']

    db.close()

    def card(s, es_admin=False):
        d = dict(s)
        estatus = d.get('estatus') or d.get('estado') or 'PENDIENTE'
        obs = d.get('observaciones_admin') or d.get('motivo') or 'Sin observaciones'
        color = {'PENDIENTE':'#ff9800','APROBADO':'#4caf50','RECHAZADO':'#f44336'}.get(estatus,'#999')
        
        btns = ""
        if estatus == 'PENDIENTE' and es_admin:
            btns = f"""
            <form method="POST" style="margin-top:10px;background:#fff3e0;padding:10px;border-radius:8px;border:2px solid #ff9800">
                <input type="hidden" name="id_solicitud" value="{d.get('id')}">
                <input name="observaciones_admin" placeholder="Observaciones..." style="width:100%;padding:8px;margin-bottom:5px">
                <button name="accion" value="aprobar" style="background:#4caf50;color:white;padding:8px 15px;border:none;border-radius:5px;margin-right:5px">✅ APROBAR</button>
                <button name="accion" value="rechazar" style="background:#f44336;color:white;padding:8px 15px;border:none;border-radius:5px">❌ RECHAZAR</button>
            </form>"""

        return f"""<div style="background:white;padding:12px;border-radius:10px;margin-bottom:10px;border-left:6px solid {color}">
        <b>#{d.get('id')} - {d.get('no_inventario','')}</b> {d.get('resguardatario_actual','')} -> <b style="color:#691C32">{d.get('resguardatario_nuevo','')}</b><br>
        <small>{d.get('solicitante','')} | {d.get('oficina_origen','')} -> {d.get('oficina_destino','')} | <b>{estatus}</b></small><br>
        <div style="background:#fff3e0;padding:6px;border-radius:5px;margin-top:5px"><b>Motivo:</b> {obs}</div>
        {btns}
        </div>"""

    # ... tu card_bp igual que tenias ...

    def card_bp(s, es_admin=False):
        import json
        d = dict(s)
        try:
            bienes = json.loads(d.get('bienes_json') or '[]')
        except:
            bienes = []
        if bienes:
            lista = "<br>".join([f"• {b.get('nombre','')} - {b.get('marca','')} {b.get('modelo','')} - Serie: {b.get('serie','')}" for b in bienes])
        else:
            lista = f"{d.get('descripcion','Sin detalle')} / Cant: {d.get('cantidad','')}"
        color = {'PENDIENTE':'#E65100','APROBADO':'#4caf50','RECHAZADO':'#f44336'}.get(d.get('estatus'),' #999')
        sid = d.get('id')
        folio = d.get('folio_num') or d.get('folio') or 'S/F'
        estatus = d.get('estatus','PENDIENTE')
        nombre_comp = d.get('nombre_completo') or d.get('usuario_solicita') or ''
        btns = ""
        if estatus == "PENDIENTE" and es_admin:
            btns = f'''
            <form method="POST" action="/aprobar_bien_propio/{sid}" style="margin-top:10px;background:#fffde7;padding:10px;border-radius:8px;border:2px solid #ff9800">
                <input name="folio_completo" placeholder="Escribe Folio POBALIN" style="width:100%;padding:10px" required>
                <button style="background:#E65100;color:white;padding:10px;width:100%;margin-top:8px;border:none;border-radius:5px;font-weight:bold">APROBAR Y GENERAR OFICIO</button>
            </form>
            <form method="POST" action="/rechazar_bien_propio/{sid}" style="margin-top:5px">
                <button style="background:#f44336;color:white;padding:8px;width:100%;border:none;border-radius:5px">RECHAZAR</button>
            </form>
            '''
        else:
            btns = f'<div style="margin-top:8px;background:#E8F5E9;padding:8px;border-radius:5px"><b>Folio:</b> {folio}</div>'
        return f'<div style="background:white;padding:14px;border-radius:10px;margin-bottom:12px;border-left:6px solid {color}"><b>#{sid} - {nombre_comp}</b> - <span style="color:{color};font-weight:bold">{estatus}</span><br><div style="margin-top:8px;background:#f9f9f9;padding:8px;border-radius:5px">{lista}</div>{btns}</div>'

    html_pend = "".join(card(s, es_admin) for s in pendientes) if pendientes else "<p style='color:#999'>No hay pendientes</p>"
    html_hist = "".join(card(s, es_admin) for s in historial) if historial else "<p style='color:#999'>Sin historial</p>"
    html_bp_pend = "".join(card_bp(s, es_admin) for s in pendientes_bp) if pendientes_bp else "<p style='color:#999'>No hay pendientes bienes propios</p>"
    html_bp_hist = "".join(card_bp(s, es_admin) for s in historial_bp) if historial_bp else "<p style='color:#999'>Sin historial bienes propios</p>"
    # --- SEPARA BAJAS DE CAMBIOS (PENDIENTES Y HISTORIAL) ---
    def es_baja(r):
        d = dict(r)
        tipo = str(d.get('tipo','')).upper()
        if 'BAJA' in tipo:
            return True
        if not d.get('resguardatario_nuevo') or str(d.get('resguardatario_nuevo')).lower() == 'none':
            return True
        return False

    pendientes_baja_lista = [r for r in pendientes if es_baja(r)]
    pendientes_cambio_lista = [r for r in pendientes if not es_baja(r)]

    historial_baja_lista = [r for r in historial if es_baja(r)]
    historial_cambio_lista = [r for r in historial if not es_baja(r)]

    html_baja = "".join(card(s, es_admin) for s in pendientes_baja_lista) if pendientes_baja_lista else "<p style='color:#999'>No hay pendientes baja</p>"
    html_pend = "".join(card(s, es_admin) for s in pendientes_cambio_lista) if pendientes_cambio_lista else "<p style='color:#999'>No hay pendientes</p>"
    
    html_hist_baja = "".join(card(s, es_admin) for s in historial_baja_lista) if historial_baja_lista else "<p style='color:#999'>Sin historial bajas</p>"
    html_hist_cambio = "".join(card(s, es_admin) for s in historial_cambio_lista) if historial_cambio_lista else "<p style='color:#999'>Sin historial</p>"
    titulo = "TODAS LAS SOLICITUDES - ADMIN" if es_admin else f"MIS SOLICITUDES - {oficina_user}"
    titulo = "TODAS LAS SOLICITUDES - ADMIN" if es_admin else f"MIS SOLICITUDES - {oficina_user}"
    html_final = f'''
    <div style="background:#fff3e0;padding:15px;border-radius:10px;border:2px solid #E65100;margin-bottom:20px">
        <h3 style="color:#E65100;margin:0">PENDIENTES - BIENES PROPIOS ({len(pendientes_bp)})</h3>
        <div style="margin-top:10px">{html_bp_pend}</div>
    </div>
    <h3>PENDIENTES - CAMBIO RESGUARDATARIO ({len(pendientes_cambio_lista)})</h3>
    {html_pend}
    <hr style="margin:25px 0">
    <h3>PENDIENTES - BAJAS ({len(pendientes_baja_lista)})</h3>
    {html_baja}
    <hr style="margin:25px 0">
    <h3>HISTORIAL BIENES PROPIOS</h3>
    {html_bp_hist}
    <hr style="margin:25px 0">
    <h3>HISTORIAL CAMBIOS RESGUARDATARIO</h3>
    {html_hist_cambio}
    <hr style="margin:25px 0">
    <h3>HISTORIAL BAJAS</h3>
    {html_hist_baja}
    '''
    final_html = f'<div style="max-width:1000px;margin:auto"><div style="background:white;padding:15px;border-radius:12px;margin-bottom:15px"><h2 style="color:#691C32;margin:0">{titulo}</h2></div>{html_final}</div>'
    return render_page(final_html)

@app.route('/bienes_propios', methods=['GET','POST'])
def bienes_propios():
    if 'username' not in session:
        return redirect('/login')
    db = get_db()
    if request.method == 'POST':
        import json
        from datetime import datetime
        bien = {
            "nombre": request.form.get('nombre','').strip().upper(),
            "marca": request.form.get('marca','').strip().upper(),
            "modelo": request.form.get('modelo','').strip().upper(),
            "color": request.form.get('color','').strip().upper(),
            "serie": request.form.get('serie','').strip().upper()
        }
        datos = {
            "nombre_completo": request.form.get('nombre_completo','').strip().upper(),
            "rfc": request.form.get('rfc','').strip().upper(),
            "domicilio": request.form.get('domicilio','').strip().upper(),
            "fecha_solicitud": datetime.now().strftime("%d de %B de %Y"),
            "bienes_json": json.dumps([bien], ensure_ascii=False)
        }
        folio_num = f"BP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        db.execute("""
        INSERT INTO bienes_propios 
        (folio_num, fecha_solicitud, nombre_completo, rfc, oficina, descripcion_bien, estatus, usuario_solicita, usuario_solicitante)
        VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            folio_num,
            datos['fecha_solicitud'],
            datos['nombre_completo'],
            datos['rfc'],
            datos['domicilio'],
            datos['bienes_json'],
            'PENDIENTE',
            session['username'],
            session['username']
        ))
        db.commit()
        db.close()
        return redirect('/mis_solicitudes')

    db.close()
    return render_page("""
<div style="max-width:650px; margin:20px auto; background:white; padding:25px; border-radius:12px; box-shadow:0 2px 10px #0001;">
<h3 style="color:#6b1c2e; text-align:center;">📦 ALTA BIENES PROPIOS - POBALIN 004</h3>

<form method="POST">
<label>Nombre completo</label>
<input type="text" name="nombre_completo" value="JUAN EDUARDO TARANGO SERRANO" style="width:100%; padding:10px; background:#eaf2ff; margin-bottom:10px; border:1px solid #ccc; border-radius:6px;" required>

<label>RFC</label>
<input type="text" name="rfc" value="TASJ9211057G8" style="width:100%; padding:10px; background:#eaf2ff; margin-bottom:10px; border:1px solid #ccc; border-radius:6px;" required>

<label>Domicilio</label>
<input type="text" name="domicilio" placeholder="SANTA CRUZ AZCAPOTZALTONGO" style="width:100%; padding:10px; background:#eaf2ff; margin-bottom:10px; border:1px solid #ccc; border-radius:6px;">

<label>Nombre del bien</label>
<input type="text" name="nombre" placeholder="Ej: BOCINAS" style="width:100%; padding:10px; background:#eaf2ff; margin-bottom:10px; border:1px solid #ccc; border-radius:6px;" required>

<label>Marca</label>
<input type="text" name="marca" placeholder="Ej: SONIC" style="width:100%; padding:10px; background:#eaf2ff; margin-bottom:10px; border:1px solid #ccc; border-radius:6px;">

<label>Modelo (si tiene, si no déjalo en blanco)</label>
<input type="text" name="modelo" placeholder="Ej: S08 / En blanco si no tiene" style="width:100%; padding:10px; background:#eaf2ff; margin-bottom:10px; border:1px solid #ccc; border-radius:6px;">

<div style="display:flex; gap:10px;">
<div style="flex:1;">
<label>Color</label>
<input type="text" name="color" placeholder="NEGRO" style="width:100%; padding:10px; border:1px solid #ccc; border-radius:6px;">
</div>
<div style="flex:1;">
<label>No. Serie</label>
<input type="text" name="serie" placeholder="051" style="width:100%; padding:10px; border:1px solid #ccc; border-radius:6px;">
</div>
</div>

<button type="submit" style="width:100%; background:#6b1c2e; color:white; padding:14px; margin-top:20px; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">ENVIAR SOLICITUD</button>
</form>
</div>
""")

@app.route('/eliminar_solicitud/<int:id_sol>')
def eliminar_solicitud(id_sol):
    if 'username' not in session: return redirect('/login')
    if session.get('rol') != 'admin': return redirect('/mis_solicitudes')
    db=get_db()
    db.execute("DELETE FROM solicitudes WHERE id=?", (id_sol,))
    db.commit()
    db.close()
    return redirect('/mis_solicitudes')
@app.route('/usuarios', methods=['GET','POST'])
@solo_admin
def usuarios_view():
    if 'username' not in session: return redirect('/login')
    db=get_db()
    # --- CANDADO A NIVEL BASE DE DATOS (se crea una sola vez) ---
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_oficina_unica_usuario ON usuarios(oficina) WHERE LOWER(rol)='usuario'")
        db.commit()
    except: pass
    
    msg=""
    if request.method=='POST':
        try:
            u = request.form.get('username','').strip().lower()
            p = request.form.get('password','').strip()
            o = request.form.get('oficina','').strip()
            r = request.form.get('rol','usuario').lower()
            if u and p and o:
                if r != 'admin':
                    # Comparamos ignorando mayusculas y espacios
                    existe = db.execute("SELECT * FROM usuarios WHERE TRIM(UPPER(oficina))=TRIM(UPPER(?)) AND LOWER(rol)='usuario'", (o,)).fetchone()
                    if existe:
                        msg = f"<div style='background:#ffcccc;color:#900;padding:12px;border-radius:8px;margin-bottom:12px;border:2px solid #900'><b>⛔ BLOQUEADO:</b> La oficina <b>{o}</b> ya tiene usuario <b>{existe['username']}</b>. Solo 1 por oficina.</div>"
                    else:
                        db.execute("INSERT INTO usuarios (username,password,rol,oficina) VALUES (?,?,?,?)",(u,p,r,o))
                        db.commit()
                        msg="<div style='background:#d4edda;color:#155724;padding:10px;border-radius:8px;margin-bottom:12px'>✅ Usuario creado</div>"
                else:
                    db.execute("INSERT INTO usuarios (username,password,rol,oficina) VALUES (?,?,?,?)",(u,p,r,o))
                    db.commit()
                    msg="<div style='background:#d4edda;padding:10px;border-radius:8px;margin-bottom:12px'>✅ Admin creado</div>"
        except Exception as e: 
            if "UNIQUE" in str(e).upper() or "idx_oficina_unica" in str(e).lower():
                msg=f"<div style='background:#ffcccc;color:#900;padding:12px;border-radius:8px;margin-bottom:12px;border:2px solid #900'><b>⛔ BLOQUEADO POR BASE DE DATOS:</b> Esa oficina ya tiene un usuario. No se puede duplicar.</div>"
            else:
                msg=f"<div style='background:#ffcccc;padding:10px;border-radius:8px;margin-bottom:12px'>Error: {e}</div>"
            print("ERROR:", e)

    lista=db.execute("SELECT * FROM usuarios").fetchall()
    oficinas=db.execute("SELECT nombre FROM oficinas").fetchall()
    db.close()
    ops=''.join([f"<option value='{o['nombre']}'>{o['nombre']}</option>" for o in oficinas])
    filas=''.join([f"<tr><td>{clean(u['username'])}</td><td>{clean(u['oficina'])}</td><td>{clean(u['password'])}</td><td>{clean(u['rol'])}</td><td><a href='/eliminar_usuario/{u['id']}' style='color:red;font-weight:bold;text-decoration:none'>Eliminar</a></td></tr>" for u in lista])
    return render_page(f"""
    <div style='background:white;padding:15px;border-radius:12px'>
      <h3>Usuarios (Solo Admin) - 1 por Oficina (Blindado)</h3>
      {msg}
      <form method='post' style='display:flex;gap:8px;flex-wrap:wrap;margin-bottom:15px'>
        <input name='username' placeholder='usuario' required style='padding:8px'>
        <input name='password' placeholder='pass' required style='padding:8px'>
        <select name='rol' style='padding:8px'><option value='usuario'>USUARIO</option><option value='admin'>ADMIN</option></select>
        <select name='oficina' required style='padding:8px'><option value=''>-- Oficina --</option>{ops}</select>
        <button style='background:#691C32;color:white;padding:8px 15px;border:none;border-radius:6px'>CREAR</button>
      </form>
      <table style='width:100%;border-collapse:collapse'><tr style='background:#691C32;color:white'><th style='padding:8px'>Usuario</th><th>Oficina</th><th>Pass</th><th>Rol</th><th>Acc</th></tr>{filas}</table>
    </div>
    """)
@app.route('/eliminar_usuario/<int:uid>')
@solo_admin
def eliminar_usuario(uid):
    if 'username' not in session: return redirect('/login')
    db=get_db(); db.execute("DELETE FROM usuarios WHERE id=?",(uid,)); db.commit(); db.close()
    return redirect('/usuarios')

# ===== PDF BONITO OFICIAL - PEGA AQUI =====
def L(t):
    return str(t or "").encode('latin-1','replace').decode('latin-1')

def header_oficial(pdf, titulo):
    pdf.set_fill_color(105,28,50)
    pdf.rect(0,0,216,20,'F')
    pdf.set_y(4)
    pdf.set_font("Arial","B",11)
    pdf.set_text_color(255,255,255)
    pdf.cell(0,6, L("SERVICIOS EDUCATIVOS INTEGRADOS AL ESTADO DE MEXICO"), align="C", ln=True)
    pdf.set_font("Arial","B",8)
    pdf.cell(0,5, L(titulo), align="C", ln=True)
    pdf.set_y(24)

def footer_firma(pdf, nombre):
    pdf.ln(10)
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.set_font("Arial","B",8)
    pdf.cell(0,5, L(f"Resguardatario: {nombre}"), align="C", ln=True)
    pdf.ln(8)
    pdf.set_font("Arial","",9)
    pdf.cell(85,5, L("______________________________"), align="C")
    pdf.cell(16,5, "")
    pdf.cell(85,5, L("______________________________"), align="C", ln=True)
    pdf.set_font("Arial","B",7)
    pdf.cell(85,4, L(nombre), align="C")
    pdf.cell(16,4, "")
    pdf.cell(85,4, L("JEFE DE OFICINA / Vo.Bo."), align="C", ln=True)
    pdf.set_font("Arial","",6)
    pdf.set_text_color(100,100,100)
    pdf.cell(0,4, L(f"Fecha: {datetime.now().strftime('%d/%m/%Y')} - Pag {pdf.page_no()}"), align="C")

@app.route('/tarjeta/<path:resguardatario>')
def tarjeta(resguardatario):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.units import inch
    import io, os, datetime

    db = get_db()
    bienes = db.execute("SELECT * FROM bienes WHERE resguardatario=? ORDER BY no_inventario", (resguardatario,)).fetchall()
    db.close()

    # Limpiar nan
    def limpia(v):
        if v is None: return ""
        s=str(v).strip()
        if s.lower() in ["nan","none","nat","null"]: return ""
        return s

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter

    # Encabezado guinda solo arriba
    c.setFillColor(colors.HexColor("#691C32"))
    c.rect(0, h-90, w, 90, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(w/2, h-35, "SERVICIOS EDUCATIVOS INTEGRADOS AL ESTADO DE MEXICO")
    c.setFont("Helvetica", 8)
    c.drawCentredString(w/2, h-50, "RESGUARDO INDIVIDUAL - Recursos Materiales y Financieros")

    # Datos
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, h-110, f"Resguardatario: {resguardatario}")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, h-125, f"Oficina: Recursos Materiales y Financieros | Total: {len(bienes)} bienes")

    # Tabla - SOLO ENCABEZADO EN GUINDA, FILAS EN BLANCO
    data = [["INVENTARIO","DESCRIPCION","MARCA","MODELO","SERIE","ESTADO"]]
    for b in bienes:
        data.append([
            limpia(b["no_inventario"]),
            limpia(b["descripcion"])[:40],
            limpia(b["marca"]),
            limpia(b["modelo"]),
            limpia(b["serie"]),
            ""
        ])

    col_widths = [70, 180, 50, 70, 70, 50]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#691C32")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 7),
        ('FONTSIZE', (0,1), (-1,-1), 6.5),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),  # <-- ESTO ES LO QUE ARREGLA, TODO BLANCO
        ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f9f9f9")]), # gris muy clarito para rayar
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
    ]))

    # Dibujar tabla
    tw, th = table.wrap(0,0)
    table.drawOn(c, 40, h-140-th)

    y_firma = h-160-th-40

    c.line(50, y_firma-30, 250, y_firma-30)
    c.drawCentredString(150, y_firma-40, resguardatario)
    
    c.line(300, y_firma-30, 500, y_firma-30)
    c.drawCentredString(400, y_firma-40, "JEFE DE OFICINA / Vo.Bo.")

    c.setFont("Helvetica", 5)
    c.drawCentredString(w/2, y_firma-50, f"Fecha: {datetime.date.today().strftime('%d/%m/%Y')} - Pag 1")

    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=False, download_name=f"Resguardo_{resguardatario}.pdf", mimetype='application/pdf')
@app.route('/tarjeta_oficina/<path:oficina>')
def tarjeta_oficina(oficina):
    if 'username' not in session: return redirect('/login')
    if session.get('rol')!='admin' and oficina!= session.get('oficina'): return redirect('/resguardos')
    con=get_db()
    bienes=con.execute("SELECT * FROM bienes WHERE oficina=? AND (en_baja=0 OR en_baja IS NULL) ORDER BY resguardatario, no_inventario",(oficina,)).fetchall()
    resgs=con.execute("SELECT DISTINCT resguardatario FROM bienes WHERE oficina=? AND resguardatario!='' ORDER BY resguardatario",(oficina,)).fetchall()
    con.close()
    pdf=FPDF(format='Letter'); pdf.set_auto_page_break(auto=True, margin=32); pdf.set_margins(12,12,12)
    for idx, r in enumerate(resgs):
        nombre=r['resguardatario']
        lista=[b for b in bienes if b['resguardatario']==nombre]
        if not lista: continue
        pdf.add_page(); header_oficial(pdf, f"RESGUARDO POR OFICINA - {oficina}")
        pdf.set_font("Arial","B",11); pdf.set_text_color(105,28,50); pdf.cell(0,8, L(f"{idx+1}. {nombre} - {len(lista)} bienes"), ln=True); pdf.ln(2)
        w=[28,62,22,22,28,24]
        pdf.set_font("Arial","B",8); pdf.set_fill_color(105,28,50); pdf.set_text_color(255,255,255)
        for i,h in enumerate(["INVENTARIO","DESCRIPCION","MARCA","MODELO","SERIE","ESTADO"]): pdf.cell(w[i],8,h,1,0,'C',True)
        pdf.ln()
        pdf.set_font("Arial","",7)
        pdf.set_text_color(0,0,0)
        for i, b in enumerate(lista):
            if i % 2 == 0:
                pdf.set_fill_color(255,255,255)
            else:
                pdf.set_fill_color(241,232,234)
            pdf.cell(w[0],6, L(b['no_inventario'])[:18],1,0,'C',True)
            pdf.cell(w[1],6, L(b['descripcion'])[:38],1,0,'L',True)
            pdf.cell(w[2],6, L(b['marca'])[:13],1,0,'C',True)
            pdf.cell(w[3],6, L(b['modelo'])[:13],1,0,'C',True)
            pdf.cell(w[4],6, L(b['serie'])[:16],1,0,'C',True)
            pdf.cell(w[5],6, L(b['estado'])[:14],1,1,'C',True)
        footer_firma(pdf, nombre)
    out=io.BytesIO(); pdf.output(out); out.seek(0)
    return send_file(out, download_name=f"Resguardos_{oficina}.pdf", as_attachment=False, mimetype='application/pdf')

@app.route('/tarjetas_todas')
def tarjetas_todas():
    if 'username' not in session: return redirect('/login')
    db=get_db()
    oficina_row = db.execute("SELECT oficina FROM usuarios WHERE username=?",(session['username'],)).fetchone()
    oficina_user = oficina_row['oficina'] if oficina_row else ''
    
    # --- FUNCION LIMPIA PARA QUITAR EL NAN ---
    def clean_nan(valor):
        if valor is None:
            return ""
        s = str(valor).strip()
        if s.lower() in ['nan','none','nat','null','']:
            return ""
        return s

    # Traes los bienes
    if session.get('rol') == 'admin' or session['username'].lower() in ['admin','aida']:
        bienes = db.execute("SELECT * FROM bienes ORDER BY resguardatario, inventario").fetchall()
    else:
        bienes = db.execute("SELECT * FROM bienes WHERE oficina=? ORDER BY resguardatario, inventario",(oficina_user,)).fetchall()
    db.close()

    # Agrupar por resguardatario
    from collections import defaultdict
    grupos = defaultdict(list)
    for b in bienes:
        grupos[b['resguardatario'] or 'SIN RESGUARDATARIO'].append(b)

    html_tablas = ""
    for resguardatario, lista in grupos.items():
        html_tablas += f"""
        <div style="page-break-inside:avoid; margin-bottom:30px">
        <h3 style="margin:10px 0; color:#333; font-size:14px">| {clean_nan(resguardatario)} | {len(lista)} bienes</h3>
        <table style="width:100%; border-collapse:collapse; font-size:10px; font-family:Arial">
            <tr style="background:#5a1a2a; color:white">
                <th style="padding:6px; border:1px solid #333; width:15%">INVENTARIO</th>
                <th style="padding:6px; border:1px solid #333; width:25%">DESCRIPCION</th>
                <th style="padding:6px; border:1px solid #333">MARCA</th>
                <th style="padding:6px; border:1px solid #333">MODELO</th>
                <th style="padding:6px; border:1px solid #333">SERIE</th>
                <th style="padding:6px; border:1px solid #333">ESTADO</th>
            </tr>
        """
        for bien in lista:
            # AQUI SE LIMPIA CADA CAMPO
            inv = clean_nan(bien['inventario'])
            desc = clean_nan(bien['descripcion'] or bien['nombre'])
            marca = clean_nan(bien['marca'])
            modelo = clean_nan(bien['modelo'])
            serie = clean_nan(bien['serie'])
            estado = clean_nan(bien['estado'] or bien['estatus'])

            html_tablas += f"""
            <tr style="background:white; color:#222">
                <td style="padding:5px; border:1px solid #999; text-align:center">{inv}</td>
                <td style="padding:5px; border:1px solid #999">{desc}</td>
                <td style="padding:5px; border:1px solid #999; text-align:center">{marca}</td>
                <td style="padding:5px; border:1px solid #999; text-align:center">{modelo}</td>
                <td style="padding:5px; border:1px solid #999; text-align:center">{serie}</td>
                <td style="padding:5px; border:1px solid #999; text-align:center">{estado}</td>
            </tr>
            """
        html_tablas += "</table></div>"

    return render_page(f"""
    <div style="background:white; padding:20px">
        <div style="background:#5a1a2a; color:white; padding:15px; text-align:center">
            <b>SERVICIOS EDUCATIVOS INTEGRADOS AL ESTADO DE MEXICO</b><br>
            <small>RESGUARDOS GENERAL - PADRON 737</small>
        </div>
        <div style="margin-top:15px">
            {html_tablas}
        </div>
    </div>
    """)

@app.route('/bajas', methods=['GET','POST'])
def bajas_modulo():
    if 'username' not in session: return redirect('/login')
    rol=session.get('rol'); oficina_user=session.get('oficina')
    con=get_db(); bien=None; mensaje=""
    if request.method=='POST':
        accion=request.form.get('accion')
        if accion=='buscar':
            inv=request.form.get('no_inventario_buscar','').strip()
            bien=con.execute("SELECT * FROM bienes WHERE no_inventario=? AND (en_baja=0 OR en_baja IS NULL)",(inv,)).fetchone()
            if not bien: mensaje="❌ No se encontró o ya está en baja"
        elif accion=='solicitar_baja':
            bien_id=request.form.get('bien_id')
            b=con.execute("SELECT * FROM bienes WHERE id=?",(bien_id,)).fetchone()
            if b:
                motivo=request.form.get('motivo','').strip()
                if not motivo:
                    mensaje="❌ Debes poner motivo"
                    bien=b
                else:
                    # CANDADO - NO DUPLICAR PENDIENTES
                    dup=con.execute("SELECT id FROM solicitudes WHERE no_inventario=? AND estatus='PENDIENTE' LIMIT 1",(b['no_inventario'],)).fetchone()
                    if dup:
                        mensaje=f"⛔ El bien {b['no_inventario']} ya tiene solicitud PENDIENTE #{dup[0]}. Espera autorización."
                        bien=b
                    else:
                        if rol=='admin':
                            con.execute("UPDATE bienes SET en_baja=1 WHERE id=?",(bien_id,))
                            con.execute("INSERT INTO solicitudes (tipo,bien_id,no_inventario,descripcion,oficina_origen,resguardatario_actual,motivo,solicitante,oficina_solicitante,estatus) VALUES (?,?,?,?,?,?,?,?,?,?)",('BAJA',b['id'],b['no_inventario'],b['descripcion'],b['oficina'],b['resguardatario'],motivo,session['username'],oficina_user,'APROBADO'))
                            con.commit()
                            mensaje="✅ BAJA directa admin realizada"
                            bien=None
                        else:
                            con.execute("INSERT INTO solicitudes (tipo,bien_id,no_inventario,descripcion,oficina_origen,resguardatario_actual,motivo,solicitante,oficina_solicitante,estatus) VALUES (?,?,?,?,?,?,?,?,?,?)",('BAJA',b['id'],b['no_inventario'],b['descripcion'],b['oficina'],b['resguardatario'],motivo,session['username'],oficina_user,'PENDIENTE'))
                            con.commit()
                            mensaje="✅ Solicitud de BAJA PENDIENTE enviada"
                            bien=None
    inventarios=con.execute("SELECT no_inventario FROM bienes WHERE (en_baja=0 OR en_baja IS NULL) ORDER BY no_inventario").fetchall()
    con.close()
    ops_inv=''.join([f"<option value='{clean(r['no_inventario'])}'>{clean(r['no_inventario'])}</option>" for r in inventarios])
    detalle=""
    if bien:
        detalle=f"""
        <div style="background:white;padding:20px;border-radius:12px;border:2px solid #b71c1c;margin-top:15px">
          <h3 style="color:#b71c1c;margin-top:0">⚠️ BIEN A DAR DE BAJA - DATOS COMPLETOS</h3>
          <table style="width:100%;border-collapse:collapse;font-size:13px">
            <tr><td style="background:#f5f5f5;padding:8px;border:1px solid #ddd;font-weight:bold;width:180px">No. Inventario</td><td style="padding:8px;border:1px solid #ddd;background:#ffebee;font-weight:bold">{clean(bien['no_inventario'])}</td></tr>
            <tr><td style="background:#f5f5f5;padding:8px;border:1px solid #ddd;font-weight:bold">Descripción</td><td style="padding:8px;border:1px solid #ddd">{clean(bien['descripcion'])}</td></tr>
            <tr><td style="background:#f5f5f5;padding:8px;border:1px solid #ddd;font-weight:bold">Marca / Modelo / Serie</td><td style="padding:8px;border:1px solid #ddd">{clean(bien['marca'])} / {clean(bien['modelo'])} / {clean(bien['serie'])}</td></tr>
            <tr><td style="background:#f5f5f5;padding:8px;border:1px solid #ddd;font-weight:bold">Resguardatario</td><td style="padding:8px;border:1px solid #ddd;font-weight:bold;color:#b71c1c">{clean(bien['resguardatario'])}</td></tr>
            <tr><td style="background:#f5f5f5;padding:8px;border:1px solid #ddd;font-weight:bold">Oficina</td><td style="padding:8px;border:1px solid #ddd">{clean(bien['oficina'])}</td></tr>
            <tr><td style="background:#f5f5f5;padding:8px;border:1px solid #ddd;font-weight:bold">Estado</td><td style="padding:8px;border:1px solid #ddd">{clean(bien['estado'])}</td></tr>
          </table>
          <form method="post" style="background:#fff3e0;padding:15px;border-radius:8px;margin-top:15px;border:1px solid #ffcc80">
            <input type="hidden" name="accion" value="solicitar_baja"><input type="hidden" name="bien_id" value="{bien['id']}">
            <label style="font-weight:bold;font-size:12px">Motivo de la baja *</label><br><textarea name="motivo" required placeholder="Ej: Bien obsoleto, dañado, inservible..." style="width:100%;padding:11px;border:2px solid #b71c1c;border-radius:6px;min-height:80px"></textarea><br>
            <button style="width:100%;padding:13px;background:#b71c1c;color:white;border:none;border-radius:6px;font-weight:bold;margin-top:8px;font-size:14px">{'DAR DE BAJA DIRECTO (ADMIN)' if rol=='admin' else 'ENVIAR SOLICITUD DE BAJA PENDIENTE'}</button>
          </form>
        </div>
        """
    return render_page(f"""<div style="max-width:900px;margin:auto"><div style="background:white;padding:20px;border-radius:12px"><h2 style="color:#b71c1c">BAJAS DE BIENES</h2><p style="font-size:12px;color:#666">Selecciona el inventario y verás todos los datos completos</p><form method="post" style="display:flex;gap:8px;margin-top:12px"><input type="hidden" name="accion" value="buscar"><input list="list_inv_baja" name="no_inventario_buscar" required placeholder="Selecciona No. Inventario" style="flex:1;padding:12px;border:2px solid #b71c1c;border-radius:8px"><button style="background:#b71c1c;color:white;padding:12px 20px;border:none;border-radius:8px;font-weight:bold">VER DATOS COMPLETOS</button></form>{'<p style="color:'+('green' if '✅' in mensaje else 'red')+';font-weight:bold;margin-top:10px;background:white;padding:10px;border-radius:6px">'+mensaje+'</p>' if mensaje else ''}</div><datalist id="list_inv_baja">{ops_inv}</datalist>{detalle}</div>""")
@app.route('/oficinas', methods=['GET','POST'])
@solo_admin
def gestionar_oficinas():
    if 'username' not in session: return redirect('/login')
    con=get_db()
    if request.method=='POST':
        if request.form.get('accion')=='crear':
            nombre=request.form.get('nombre','').strip().upper()
            if nombre:
                try: con.execute("INSERT INTO oficinas (nombre) VALUES (?)",(nombre,)); con.commit()
                except: pass
        elif request.form.get('accion')=='eliminar':
            con.execute("DELETE FROM oficinas WHERE id=?",(request.form.get('id'),)); con.commit()
    oficinas=con.execute("SELECT * FROM oficinas ORDER BY nombre").fetchall()
    con.close()
    filas="".join([f"<tr><td>{o['id']}</td><td>{o['nombre']}</td><td><form method='post'><input type='hidden' name='accion' value='eliminar'><input type='hidden' name='id' value='{o['id']}'><button style='background:#f44336;color:white;border:none;padding:5px 8px;border-radius:4px'>Eliminar</button></form></td></tr>" for o in oficinas])
    return render_page(f"""<div style="background:white;padding:20px;border-radius:12px"><h2>OFICINAS - Solo Admin</h2><form method="post" style="display:flex;gap:8px;margin:15px 0"><input type="hidden" name="accion" value="crear"><input name="nombre" required placeholder="Nueva oficina" style="flex:1;padding:10px"><button style="background:#2e7d32;color:white;padding:10px 15px;border:none;border-radius:6px">CREAR</button></form><table style="width:100%"><tr style="background:#691C32;color:white"><th>ID</th><th>Nombre</th><th>Acc</th></tr>{filas}</table></div>""")

@app.route('/eliminar_seleccionadas', methods=['POST'])
def eliminar_seleccionadas():
    if session.get('rol') != 'admin':
        return redirect('/login')
    ids = request.form.getlist('ids')
    if ids:
        db = get_db()
        q = ','.join(['?']*len(ids))
        db.execute(f"DELETE FROM solicitudes WHERE id IN ({q})", ids)
        db.commit()
        db.close()
    return redirect('/mis_solicitudes')
# --- RUTA PARA APROBAR BIEN PROPIO Y PONER EL FOLIO COMPLETO ---
import json, os, ast
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from datetime import datetime

def generar_oficio_respuesta_bien_propio(solicitud, folio_completo, bienes_lista):
    # --- 1. NORMALIZA BIENES (soporta MAYUSCULAS y minusculas) ---
    bienes_final = []
    for b in bienes_lista or []:
        if isinstance(b, str):
            try:
                b = json.loads(b)
            except:
                try:
                    b = ast.literal_eval(b)
                except:
                    b = {'nombre': b}
        if isinstance(b, dict):
            nb = {str(k).lower(): v for k, v in b.items()}
            bienes_final.append({
                'nombre': nb.get('nombre') or nb.get('descripcion') or '',
                'marca': nb.get('marca') or '',
                'modelo': nb.get('modelo') or '',
                'serie': nb.get('serie') or nb.get('no_serie') or nb.get('num_serie') or '',
                'color': nb.get('color') or '',
            })
    
    if not bienes_final:
        bienes_final = [{
            'nombre': solicitud.get('descripcion') or solicitud.get('descripcion_bien') or 'BIEN PROPIO',
            'marca': solicitud.get('marca',''),
            'modelo': solicitud.get('modelo',''),
            'serie': solicitud.get('serie') or solicitud.get('no_serie') or '',
            'color': solicitud.get('color',''),
        }]

    # --- 2. ABRE PLANTILLA ---
    ruta_plantilla = os.path.join(os.getcwd(), 'plantilla_bienes_propios.docx')
    if not os.path.exists(ruta_plantilla):
        ruta_plantilla = 'plantilla_bienes_propios.docx'
    
    if os.path.exists(ruta_plantilla):
        doc = Document(ruta_plantilla)
    else:
        doc = Document()
        doc.add_paragraph("GOBIERNO DEL ESTADO DE MEXICO | EDUCACIÓN | SEIEM")
        doc.add_paragraph(f"Metepec, Estado de México, a {datetime.now().day} de {datetime.now().month} de {datetime.now().year}\n{folio_completo}")
        doc.add_paragraph(f"{solicitud.get('nombre_completo','').upper()}\nRFC: {solicitud.get('rfc','')}\nPRESENTE.")
        tabla = doc.add_table(rows=1, cols=6)
        tabla.style = 'Table Grid'
        hdr = tabla.rows[0].cells
        hdr[0].text = 'N.P.'; hdr[1].text = 'Descripción del bien'; hdr[2].text = 'Marca'; hdr[3].text = 'Modelo'; hdr[4].text = 'Serie'; hdr[5].text = 'COLOR'
        doc._tabla_bienes = tabla

    nombre = str(solicitud.get('nombre_completo','')).strip().upper()
    rfc = str(solicitud.get('rfc','')).strip().upper()
    fecha_sol = solicitud.get('fecha_solicitud','') or datetime.now().strftime("%d/%m/%Y")

    # --- 3. REEMPLAZA DATOS EN LA PLANTILLA ---
    meses = {'january':'enero','february':'febrero','march':'marzo','april':'abril','may':'mayo','june':'junio','july':'julio','august':'agosto','september':'septiembre','october':'octubre','november':'noviembre','december':'diciembre'}
    for p in doc.paragraphs:
        txt_low = p.text.lower()
        if "metepec" in txt_low:
            mes_en = datetime.now().strftime('%B').lower()
            mes_es = meses.get(mes_en, mes_en)
            p.text = f"Metepec, Estado de México, a {datetime.now().day} de {mes_es} de {datetime.now().year}"
        if "228c01" in txt_low:
            p.text = folio_completo
            if p.runs: p.runs[0].bold = True
        if "néstor" in txt_low or "rodríguez" in txt_low or (p.text.strip().upper().startswith("D.E.") and len(p.text) < 150):
            p.text = f"{nombre}\nRFC: {rfc}\nP R E S E N T E."
        if "en atención a su solicitud de fecha" in txt_low:
            p.text = f"En atención a su solicitud de fecha {fecha_sol}, informo a usted que se autoriza el ingreso de los artículos descritos, siempre y cuando su uso o instalación no altere las subestructuras establecidas en el edificio que ocupa esta Dirección."

    # --- 4. LLENA TABLA ---
    tabla = getattr(doc, '_tabla_bienes', None)
    if not tabla:
        for t in doc.tables:
            txt = " ".join([c.text for r in t.rows for c in r.cells]).upper()
            if "DESCRIP" in txt and "MARCA" in txt:
                tabla = t
                break
        if not tabla and doc.tables:
            tabla = doc.tables[0]

    if tabla:
        while len(tabla.rows) > 1:
            tr = tabla.rows[1]._tr
            tr.getparent().remove(tr)
        for i, b in enumerate(bienes_final, 1):
            row = tabla.add_row().cells
            row[0].text = str(i)
            row[1].text = str(b.get('nombre','')).upper()
            row[2].text = str(b.get('marca','')).upper()
            row[3].text = str(b.get('modelo','')).upper()
            row[4].text = str(b.get('serie','')).upper()
            row[5].text = str(b.get('color','')).upper()

    os.makedirs('oficios', exist_ok=True)
    nombre_archivo = f"{folio_completo.replace('/','_')}_{rfc}.docx"
    ruta = os.path.join('oficios', nombre_archivo)
    doc.save(ruta)
    return ruta

@app.route('/aprobar_bien_propio/<int:id_sol>', methods=['POST'])
def aprobar_bien_propio(id_sol):
    if 'username' not in session: 
        return redirect('/login')
    db = get_db()
    folio_completo = request.form.get('folio_completo','').strip()
    if not folio_completo:
        db.close()
        return "Falta folio", 400
    sol = db.execute("SELECT * FROM bienes_propios WHERE id=?", (id_sol,)).fetchone()
    if not sol:
        db.close()
        return "No existe", 404
    try:
        bienes_lista = json.loads(sol['bienes_json']) if sol['bienes_json'] else []
    except:
        bienes_lista = []
    ruta_doc = generar_oficio_respuesta_bien_propio(dict(sol), folio_completo, bienes_lista)
    fecha_resp = datetime.now().strftime("%d/%m/%Y %H:%M")
    db.execute("UPDATE bienes_propios SET estatus='APROBADO', folio_num=?, fecha_respuesta=? WHERE id=?",
               (folio_completo, fecha_resp, id_sol))
    db.commit()
    db.close()
    return redirect(f'/oficios/{os.path.basename(ruta_doc)}')

@app.route('/rechazar_bien_propio/<int:id_sol>', methods=['POST'])
def rechazar_bien_propio(id_sol):
    if 'username' not in session:
        return redirect('/login')
    db = get_db()
    fecha_resp = datetime.now().strftime("%d/%m/%Y %H:%M")
    db.execute("UPDATE bienes_propios SET estatus='RECHAZADO', fecha_respuesta=? WHERE id=?", (fecha_resp, id_sol))
    db.commit()
    db.close()
    return redirect('/mis_solicitudes')
@app.route('/oficios/<path:filename>')
def servir_oficio(filename):
    from flask import send_from_directory
    import os
    dir_oficios = os.path.join(os.getcwd(), 'oficios')
    os.makedirs(dir_oficios, exist_ok=True)
    return send_from_directory(dir_oficios, filename, as_attachment=True)

@app.route('/descargar_oficio_bp/<int:id_sol>')
def descargar_oficio_bp(id_sol):
    db=get_db()
    sol=db.execute("SELECT * FROM bienes_propios WHERE id=?",(id_sol,)).fetchone()
    db.close()
    if not sol or not sol['folio_num']:
        return "Sin oficio",404
    import os, json
    try:
        bienes_lista = json.loads(sol['bienes_json']) if sol['bienes_json'] else []
    except:
        bienes_lista=[]
    ruta_doc = generar_oficio_respuesta_bien_propio(dict(sol), sol['folio_num'], bienes_lista)
    nombre=os.path.basename(ruta_doc)
    return redirect(f'/oficios/{nombre}')

@app.route('/eliminar_bien_propio/<int:id_sol>')
def eliminar_bien_propio(id_sol):
    if 'username' not in session:
        return redirect('/login')
    db = get_db()
    db.execute("DELETE FROM bienes_propios WHERE id=?", (id_sol,))
    db.commit()
    db.close()
    return redirect('/mis_solicitudes')
@app.route('/eliminar_bien_propio_aprobado/<int:id_sol>')
def eliminar_bien_propio_aprobado(id_sol):
    if 'username' not in session:
        return redirect('/login')
    db = get_db()
    db.execute("DELETE FROM bienes_propios WHERE id=?", (id_sol,))
    db.commit()
    db.close()
    return redirect('/mis_solicitudes')
@app.route('/agregar_bien', methods=['POST'])
def agregar_bien():
    if 'username' not in session:
        return redirect('/login')
    db=get_db()
    no_inv=request.form.get('no_inventario','').strip().upper()
    desc=request.form.get('descripcion','').strip().upper()
    db.execute("INSERT INTO bienes (no_inventario, descripcion, marca, modelo, serie, oficina, resguardatario, en_baja) VALUES (?,?,?,?,?,?,?,0)",
    (no_inv, desc, request.form.get('marca','').strip().upper(), request.form.get('modelo','').strip().upper(), request.form.get('serie','').strip().upper(), request.form.get('oficina','').strip(), request.form.get('resguardatario','').strip().upper()))
    db.commit()
    db.close()
    return redirect(url_for('dashboard'))
# ===== VERIFICACION FISICA - SOLO ADMIN - SE CREA SOLA =====
def crear_tabla_verificacion():
    con=get_db()
    con.execute("""
    CREATE TABLE IF NOT EXISTS verificaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bien_id INTEGER,
        no_inventario TEXT,
        descripcion TEXT,
        resguardatario TEXT,
        oficina TEXT,
        estatus_verificacion TEXT,
        comentario TEXT,
        verificador TEXT,
        fecha_verificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    try: con.execute("ALTER TABLE bienes ADD COLUMN ultima_verificacion DATE")
    except: pass
    try: con.execute("ALTER TABLE bienes ADD COLUMN estatus_fisico TEXT")
    except: pass
    con.commit()
    con.close()

@app.route('/verificacion', methods=['GET','POST'])
def verificacion():
    if 'username' not in session: return redirect('/login')
    if session.get('rol') != 'admin':
        return render_page("<div style='max-width:600px;margin:50px auto;background:white;padding:30px;border-radius:12px;text-align:center'><h2>⛔ Solo Administrador</h2><a href='/'>Volver</a></div>")

    crear_tabla_verificacion() # se crea sola la primera vez
    con=get_db(); bien=None; mensaje=""
    if request.method=='POST':
        accion=request.form.get('accion')
        if accion=='buscar':
            inv=request.form.get('no_inventario_buscar','').strip()
            bien=con.execute("SELECT * FROM bienes WHERE no_inventario=? AND (en_baja=0 OR en_baja IS NULL)",(inv,)).fetchone()
            if not bien: mensaje="❌ No se encontró"
        elif accion=='guardar':
            bien_id=request.form.get('bien_id')
            b=con.execute("SELECT * FROM bienes WHERE id=?",(bien_id,)).fetchone()
            if b:
                estatus=request.form.get('estatus_fisico')
                coment=request.form.get('comentario','').strip()
                con.execute("INSERT INTO verificaciones (bien_id,no_inventario,descripcion,resguardatario,oficina,estatus_verificacion,comentario,verificador) VALUES (?,?,?,?,?,?,?,?)",
                            (b['id'],b['no_inventario'],b['descripcion'],b['resguardatario'],b['oficina'],estatus,coment,session['username']))
                con.execute("UPDATE bienes SET ultima_verificacion=date('now'), estatus_fisico=? WHERE id=?",(estatus,b['id']))
                con.commit()
                mensaje=f"✅ {b['no_inventario']} marcado como {estatus}"
                bien=None

    inventarios=con.execute("SELECT no_inventario FROM bienes WHERE (en_baja=0 OR en_baja IS NULL) ORDER BY no_inventario").fetchall()
    total=con.execute("SELECT COUNT(*) FROM bienes WHERE (en_baja=0 OR en_baja IS NULL)").fetchone()[0]
    verif=con.execute("SELECT COUNT(DISTINCT no_inventario) FROM verificaciones").fetchone()[0]
    con.close()
    
    ops=''.join([f"<option value='{clean(r['no_inventario'])}'>{clean(r['no_inventario'])}</option>" for r in inventarios])
    detalle=""
    if bien:
        detalle=f"""
        <div style="background:white;padding:20px;border-radius:12px;border:2px solid #1565c0;margin-top:15px">
          <h3>{clean(bien['no_inventario'])} - {clean(bien['descripcion'])}</h3>
          <p><b>Marca:</b> {clean(bien['marca'])} | <b>Serie:</b> {clean(bien['serie'])}<br>
          <b>Resguardatario:</b> {clean(bien['resguardatario'])} | <b>Oficina:</b> {clean(bien['oficina'])}</p>
          <form method="post" style="background:#e3f2fd;padding:15px;border-radius:8px">
            <input type="hidden" name="accion" value="guardar"><input type="hidden" name="bien_id" value="{bien['id']}">
            <label><b>Estatus físico *</b></label><br>
            <select name="estatus_fisico" required style="width:100%;padding:12px;border:2px solid #1565c0;border-radius:8px">
              <option value="UBICADO">✅ UBICADO</option>
              <option value="NO LOCALIZADO">❌ NO LOCALIZADO</option>
              <option value="DAÑADO">⚠️ DAÑADO</option>
              <option value="PRESTADO">🔄 PRESTADO</option>
            </select><br><br>
            <textarea name="comentario" placeholder="Ubicación exacta..." style="width:100%;min-height:60px;padding:10px"></textarea><br>
            <button style="width:100%;padding:13px;background:#1565c0;color:white;border:none;border-radius:8px;font-weight:bold;margin-top:8px">GUARDAR COMO REVISADO</button>
          </form>
        </div>"""
    return render_page(f"""
    <div style="max-width:900px;margin:auto">
      <div style="background:white;padding:20px;border-radius:12px">
        <h2 style="color:#1565c0">📋 VERIFICACIÓN FÍSICA (ADMIN)</h2>
        <p>Total: <b>{total}</b> | Verificados: <b style="color:green">{verif}</b> | Faltan: <b style="color:red">{total-verif}</b></p>
        <a href="/exportar_faltantes" style="background:#2e7d32;color:white;padding:8px 14px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:13px;display:inline-block;margin-bottom:10px">📥 EXPORTAR FALTANTES A EXCEL ({total-verif})</a>
        <form method="post" style="display:flex;gap:8px">
          <input type="hidden" name="accion" value="buscar">
          <input list="lista_inv" name="no_inventario_buscar" required placeholder="Escribe No. Inventario" style="flex:1;padding:12px;border:2px solid #1565c0;border-radius:8px">
          <button style="background:#1565c0;color:white;padding:12px 20px;border:none;border-radius:8px;font-weight:bold">VER DATOS</button>
        </form>
        {'<p style="color:green;font-weight:bold;margin-top:10px">'+mensaje+'</p>' if mensaje else ''}
      </div>
      <datalist id="lista_inv">{ops}</datalist>
      {detalle}
    </div>""")
from flask import send_file
import io
from openpyxl import Workbook

@app.route('/exportar_faltantes')
def exportar_faltantes():
    if 'username' not in session or session.get('rol') != 'admin':
        return redirect('/login')
    
    con=get_db()
    # Los que NO están en verificaciones
    faltantes=con.execute("""
        SELECT no_inventario, descripcion, serie, marca, modelo, 
               resguardatario, oficina
        FROM bienes 
        WHERE no_inventario NOT IN (SELECT no_inventario FROM verificaciones)
        AND (en_baja=0 OR en_baja IS NULL)
        ORDER BY oficina, resguardatario
    """).fetchall()
    con.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Faltantes por verificar"
    # Encabezados
    ws.append(["No. Inventario","Descripción","Serie","Marca","Modelo","Resguardatario","Oficina"])
    for r in faltantes:
        ws.append([r['no_inventario'], r['descripcion'], r['serie'], r['marca'], r['modelo'], r['resguardatario'], r['oficina']])
    
    # Guardar en memoria
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(output, download_name=f"faltantes_por_verificar_{len(faltantes)}.xlsx", as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
