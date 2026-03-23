import numpy as np
import cv2
from skimage.measure import marching_cubes
import scipy.ndimage
import trimesh
import io
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, Response

app = FastAPI()

# ==========================================
# 1. HTML / JS ФРОНТЕНД (PRO Интерфейс)
# ==========================================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>SDF Shadow Lamp Generator Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="importmap">
      {
        "imports": {
          "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
          "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
        }
      }
    </script>
    <style>
        body { margin: 0; overflow: hidden; background: #0b0f19; color: #f8fafc; font-family: sans-serif; }
        #renderCanvas { width: 100%; height: 100vh; display: block; }
        #ui-panel {
            position: absolute; top: 0; left: 0; width: 400px; height: 100vh;
            background: rgba(15, 23, 42, 0.95); padding: 25px 25px; overflow-y: auto;
            backdrop-filter: blur(15px); border-right: 1px solid #1e293b;
            box-shadow: 10px 0 30px rgba(0,0,0,0.8);
        }
        .slider-label { display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 5px; color: #94a3b8; font-weight: 600;}
        input[type=range] { width: 100%; margin-bottom: 15px; accent-color: #0ea5e9; }
        .group-title { margin-top: 25px; margin-bottom: 12px; font-size: 1.05rem; font-weight: 800; color: #38bdf8; text-transform: uppercase; letter-spacing: 1px; border-bottom: 2px solid #1e293b; padding-bottom: 4px; }
        #loading { display: none; margin-top: 15px; color: #10b981; font-weight: bold; text-align: center; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #38bdf8; border-radius: 5px; }
    </style>
</head>
<body>

<div id="ui-panel">
    <h1 class="text-3xl font-black mb-1 text-white tracking-tight">SHADOW <span class="text-sky-500">LAMP</span></h1>
    <p class="text-xs text-slate-400 mb-6 font-mono">v2.0 // SDF Perfect Geometry</p>
    
    <form id="gen-form">
        <label class="block text-sm font-bold mb-2 text-slate-200">Изображение / Трафарет:</label>
        <input type="file" id="imageInput" accept="image/png, image/jpeg" class="mb-2 text-sm w-full file:mr-3 file:py-2 file:px-4 file:rounded-md file:border-0 file:font-bold file:bg-sky-600 file:text-white hover:file:bg-sky-500 transition"/>

        <div class="group-title">Базовый цилиндр</div>
        <div class="slider-label"><span>Внешний радиус (мм)</span><span id="v-rout" class="text-white">35</span></div>
        <input type="range" id="r_out" min="20" max="80" value="35" oninput="document.getElementById('v-rout').innerText=this.value">

        <div class="slider-label"><span>Толщина стенок (мм)</span><span id="v-thick" class="text-white">2.0</span></div>
        <input type="range" id="thickness" min="0.5" max="5.0" step="0.1" value="2.0" oninput="document.getElementById('v-thick').innerText=this.value">

        <div class="slider-label"><span>Высота основы (мм)</span><span id="v-h" class="text-white">70</span></div>
        <input type="range" id="h" min="20" max="150" value="70" oninput="document.getElementById('v-h').innerText=this.value">

        <div class="group-title text-fuchsia-400">Форма горлышка (Новое)</div>
        <div class="slider-label"><span>Высота скоса (мм)</span><span id="v-neck-h" class="text-white">20</span></div>
        <input type="range" id="neck_h" min="0" max="100" value="20" oninput="document.getElementById('v-neck-h').innerText=this.value">
        
        <div class="slider-label"><span>Верхний радиус горлышка (мм)</span><span id="v-neck-r" class="text-white">15</span></div>
        <input type="range" id="neck_r" min="5" max="80" value="15" oninput="document.getElementById('v-neck-r').innerText=this.value">

        <div class="slider-label"><span>Высота верхнего обода (мм)</span><span id="v-top-h" class="text-white">10</span></div>
        <input type="range" id="top_h" min="0" max="50" value="10" oninput="document.getElementById('v-top-h').innerText=this.value">

        <div class="group-title text-emerald-400">Оптика и Опоры</div>
        <div class="slider-label"><span>Высота лампочки внутри (мм)</span><span id="v-lz" class="text-white">60</span></div>
        <input type="range" id="l_z" min="10" max="200" value="60" oninput="updateLight(); document.getElementById('v-lz').innerText=this.value">

        <div class="slider-label"><span>Размер тени на столе (мм)</span><span id="v-proj" class="text-white">200</span></div>
        <input type="range" id="proj_w" min="50" max="600" value="200" oninput="document.getElementById('v-proj').innerText=this.value">

        <div class="slider-label"><span class="text-emerald-400">Кол-во опор каркаса</span><span id="v-pil" class="text-white">4</span></div>
        <input type="range" id="num_pillars" min="0" max="16" value="4" oninput="document.getElementById('v-pil').innerText=this.value">
        
        <div class="slider-label"><span class="text-emerald-400">Ширина ТЕНИ от опоры (мм)</span><span id="v-pw" class="text-white">4.0</span></div>
        <input type="range" id="pillar_width" min="1.0" max="15.0" step="0.5" value="4.0" oninput="document.getElementById('v-pw').innerText=this.value">

        <div class="group-title text-amber-400">Рендер (Качество)</div>
        <div class="slider-label"><span class="text-amber-400">Сглаживание контуров (SDF)</span><span id="v-sm" class="text-white">1.5</span></div>
        <input type="range" id="smooth_2d" min="0.0" max="5.0" step="0.1" value="1.5" oninput="document.getElementById('v-sm').innerText=this.value">

        <div class="slider-label"><span>Разрешение 3D сетки</span><span id="v-res" class="text-white">160</span></div>
        <input type="range" id="res" min="80" max="400" value="160" oninput="document.getElementById('v-res').innerText=this.value">

        <button type="submit" class="w-full mt-6 bg-sky-600 hover:bg-sky-500 text-white font-black py-4 px-4 rounded-lg shadow-[0_0_15px_rgba(14,165,233,0.5)] transform transition hover:scale-[1.03]">
            🚀 СГЕНЕРИРОВАТЬ STL
        </button>
        <div id="loading">Просчет SDF полей... (10-30 сек)</div>
    </form>

    <button id="downloadBtn" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-black py-4 px-4 rounded-lg mt-4 hidden shadow-[0_0_15px_rgba(16,185,129,0.5)] transition hover:scale-[1.03]">
        📥 СКАЧАТЬ МОДЕЛЬ
    </button>
</div>

<script type="module">
    import * as THREE from 'three';
    import { STLLoader } from 'three/addons/loaders/STLLoader.js';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

    // Сцена
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, window.innerWidth / window.innerHeight, 1, 1500);
    camera.position.set(-150, 180, 250);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setClearColor(0x0b0f19); 
    document.body.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 40, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Окружение
    scene.add(new THREE.AmbientLight(0x1e293b, 1.5));

    // Лампа
    const pointLight = new THREE.PointLight(0xfff5e6, 8000, 1000);
    pointLight.castShadow = true;
    pointLight.shadow.mapSize.width = 4096; // 4K тени для идеальной резкости
    pointLight.shadow.mapSize.height = 4096;
    pointLight.shadow.bias = -0.0005;
    scene.add(pointLight);

    const bulb = new THREE.Mesh(new THREE.SphereGeometry(2, 32, 32), new THREE.MeshBasicMaterial({ color: 0xffffff }));
    scene.add(bulb);

    // Стол
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(1000, 1000), new THREE.MeshStandardMaterial({ color: 0xe2e8f0, roughness: 0.9 }));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    let lampMesh = null;
    let stlBlobUrl = null;

    window.updateLight = function() {
        const lz = parseFloat(document.getElementById('l_z').value);
        pointLight.position.set(0, lz, 0);
        bulb.position.set(0, lz, 0);
    };
    updateLight();

    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();

    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    document.getElementById('gen-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        document.getElementById('loading').style.display = 'block';
        document.getElementById('downloadBtn').classList.add('hidden');

        const formData = new FormData();
        const fileInput = document.getElementById('imageInput');
        if(fileInput.files.length > 0) formData.append('file', fileInput.files[0]);
        
        formData.append('r_out', document.getElementById('r_out').value);
        formData.append('thickness', document.getElementById('thickness').value);
        formData.append('h', document.getElementById('h').value);
        formData.append('neck_h', document.getElementById('neck_h').value);
        formData.append('neck_r', document.getElementById('neck_r').value);
        formData.append('top_h', document.getElementById('top_h').value);
        formData.append('l_z', document.getElementById('l_z').value);
        formData.append('proj_w', document.getElementById('proj_w').value);
        formData.append('num_pillars', document.getElementById('num_pillars').value);
        formData.append('pillar_width', document.getElementById('pillar_width').value);
        formData.append('smooth_2d', document.getElementById('smooth_2d').value);
        formData.append('res', document.getElementById('res').value);

        try {
            const response = await fetch('/generate', { method: 'POST', body: formData });
            if (!response.ok) throw new Error("Ошибка сервера при генерации!");
            
            const blob = await response.blob();
            if(lampMesh) { scene.remove(lampMesh); lampMesh.geometry.dispose(); lampMesh.material.dispose(); }
            if(stlBlobUrl) URL.revokeObjectURL(stlBlobUrl);

            stlBlobUrl = URL.createObjectURL(blob);
            
            const loader = new STLLoader();
            loader.load(stlBlobUrl, function (geometry) {
                geometry.computeVertexNormals(); // Идеальные нормали для рендера
                const material = new THREE.MeshStandardMaterial({ 
                    color: 0x38bdf8, roughness: 0.2, metalness: 0.1, side: THREE.DoubleSide
                });
                lampMesh = new THREE.Mesh(geometry, material);
                lampMesh.rotation.x = -Math.PI / 2;
                lampMesh.castShadow = true;
                lampMesh.receiveShadow = true;
                scene.add(lampMesh);

                document.getElementById('loading').style.display = 'none';
                document.getElementById('downloadBtn').classList.remove('hidden');
            });
        } catch (err) { alert(err); document.getElementById('loading').style.display = 'none'; }
    });

    document.getElementById('downloadBtn').addEventListener('click', () => {
        if(!stlBlobUrl) return;
        const a = document.createElement('a');
        a.href = stlBlobUrl;
        a.download = 'sdf_shadow_lamp.stl';
        a.click();
    });
</script>
</body>
</html>
"""

# ==========================================
# 2. БЕКЭНД (SDF CAD Генератор)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    return HTML_CONTENT

@app.post("/generate")
async def generate_lamp(
    file: UploadFile = File(None),
    r_out: float = Form(...), thickness: float = Form(...),
    h: float = Form(...), neck_h: float = Form(...), neck_r: float = Form(...), top_h: float = Form(...),
    l_z: float = Form(...), proj_w: float = Form(...),
    num_pillars: int = Form(...), pillar_width: float = Form(...),
    smooth_2d: float = Form(...), res: int = Form(...)
):
    # Загрузка и подготовка изображения
    if file is not None and file.filename != "":
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    else:
        # Крутой тестовый рисунок, если картинка не загружена
        img = np.zeros((800, 800), dtype=np.uint8)
        cv2.circle(img, (400, 400), 300, 255, 30)
        cv2.putText(img, "SDF", (200, 450), cv2.FONT_HERSHEY_TRIPLEX, 7.0, 255, 25)

    # 2D Сглаживание маски (Anti-aliasing) 
    # Превращает пиксели в непрерывное векторное поле
    img_float = img.astype(float) / 255.0
    if smooth_2d > 0:
        img_float = scipy.ndimage.gaussian_filter(img_float, sigma=smooth_2d)

    img_w, img_h = img_float.shape[1], img_float.shape[0]

    # === РАСЧЕТ ИЗОТРОПНОЙ 3D СЕТКИ ===
    total_H = h + neck_h + top_h
    max_radius = max(r_out, neck_r)
    
    # Чтобы кубики были ровными (без вытяжений), вычисляем точный размер вокселя
    voxel_size = (max_radius * 2 + 4) / res
    res_z = max(10, int(total_H / voxel_size))

    x = np.linspace(-max_radius - 2, max_radius + 2, res)
    y = np.linspace(-max_radius - 2, max_radius + 2, res)
    z = np.linspace(0, total_H, res_z)
    
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
    R_3d = np.sqrt(X**2 + Y**2)

    # === ПОСТРОЕНИЕ ОБОЛОЧКИ ЛАМПЫ (Neck + Cylinder) ===
    # Вычисляем радиусы непрерывно для каждого слоя Z
    R_out_Z = np.full_like(Z, r_out)
    
    # Маска скоса (конуса)
    neck_mask = (Z > h) & (Z <= h + neck_h)
    if neck_h > 0:
        t = (Z[neck_mask] - h) / neck_h
        R_out_Z[neck_mask] = r_out * (1 - t) + neck_r * t
        
    # Маска верхнего кольца
    top_mask = (Z > h + neck_h)
    R_out_Z[top_mask] = neck_r

    R_in_Z = R_out_Z - thickness
    
    # Основная SDF-функция стены (Положительная внутри материала)
    sdf_wall = np.minimum(R_out_Z - R_3d, R_3d - R_in_Z)

    # === ОПТИЧЕСКАЯ ПРОЕКЦИЯ ЛУЧЕЙ ===
    Z_safe = np.where(Z >= l_z, -1e9, Z) # Защита от обратных лучей
    X_proj = X * l_z / (l_z - Z_safe)
    Y_proj = Y * l_z / (l_z - Z_safe)

    U = (X_proj + proj_w / 2) / proj_w * (img_w - 1)
    V = (img_h - 1) - (Y_proj + proj_w / 2) / proj_w * (img_h - 1)

    # Чтение картинки как непрерывного поля (order=1 - билинейная интерполяция)
    # cval=0.0 означает, что за пределами картинки всё будет залито пластиком
    img_val = scipy.ndimage.map_coordinates(img_float, [V, U], order=1, cval=0.0)
    
    # Переводим яркость в дистанцию (0.5 = граница поверхности)
    sdf_img = (0.5 - img_val) * 2.0 

    # === РАСЧЕТ ОПОР (Pillars) В ПРОСТРАНСТВЕ ТЕНИ ===
    if num_pillars > 0:
        angle_rad = np.arctan2(Y_proj, X_proj)
        segment = 2 * np.pi / num_pillars
        angle_diff = angle_rad - np.round(angle_rad / segment) * segment
        R_proj = np.sqrt(X_proj**2 + Y_proj**2)
        
        # Дистанция от луча до центра столба ПРЯМО НА ПОЛУ
        dist_proj = R_proj * np.abs(np.sin(angle_diff))
        
        # SDF столба: если dist < width/2, мы внутри столба
        sdf_pillars = (pillar_width / 2.0) - dist_proj
    else:
        sdf_pillars = np.full_like(Z, -1.0)

    # Объединяем картинку и опорные столбы
    sdf_pattern = np.maximum(sdf_img, sdf_pillars)
    
    # Вырезаем узор на цилиндре
    sdf_cut = np.minimum(sdf_wall, sdf_pattern)

    # Защищаем верхние и нижние элементы от вырезания
    # Z < 2.0 (дно), Z > h - 2.0 (начало горлышка), Z >= l_z - 0.1 (выше света)
    is_solid = (Z < 2.0) | (Z > h - 2.0) | (Z >= l_z - 0.1)
    
    # Финальная геометрия
    final_sdf = np.where(is_solid, sdf_wall, sdf_cut)

    # === ИДЕАЛЬНЫЙ MARCHING CUBES ПО SDF-ПОЛЮ ===
    # level=0.0 находит точные, суб-миллиметровые границы!
    verts, faces, normals, values = marching_cubes(
        final_sdf, level=0.0, spacing=(x[1]-x[0], y[1]-y[0], z[1]-z[0])
    )
    
    verts[:, 0] += x[0]
    verts[:, 1] += y[0]
    verts[:, 2] += z[0]

    mesh = trimesh.Trimesh(vertices=verts, faces=faces)

    stl_io = io.BytesIO()
    mesh.export(file_obj=stl_io, file_type='stl')
    stl_io.seek(0)

    return Response(content=stl_io.read(), media_type="application/vnd.ms-pki.stl")

if __name__ == "__main__":
    print("🚀 ПРО СЕРВЕР ЗАПУЩЕН! Открой в браузере: http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
