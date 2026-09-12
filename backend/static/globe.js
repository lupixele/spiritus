/**
 * Spiritus Visual Observatory Globe.
 * 
 * Derived from Astra Three.js architecture:
 * - Day/Night texture mapping with specular ocean highlights
 * - Sun direction illumination & subtle atmospheric limb
 * - Starfield particle system (dark mode) & soft studio canvas (light mode)
 * - Earthquake & Wildfire hazard point markers
 * - Visakhapatnam operational exercise target marker
 * - Low-end hardware optimization: DPR capped at 1.0, 32x32 segments,
 *   render pause on visibility hidden, smooth inertial orbit controls.
 */
import * as THREE from './vendor/three.module.js';
import { latLonToXYZ } from './geo.js';

const TAU = Math.PI * 2;

function makeStars(count = 1200) {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const radius = 12 + Math.random() * 16;
    const theta = Math.random() * TAU;
    const phi = Math.acos(Math.random() * 2 - 1);
    positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = radius * Math.cos(phi);
    positions[i * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
    
    // Cool mint & white stars
    const brightness = 0.5 + Math.random() * 0.5;
    colors[i * 3] = brightness * 0.9;
    colors[i * 3 + 1] = brightness;
    colors[i * 3 + 2] = brightness * 1.1;
  }
  const geom = new THREE.BufferGeometry();
  geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  return new THREE.Points(
    geom,
    new THREE.PointsMaterial({ size: 0.035, vertexColors: true, transparent: true, opacity: 0.75 })
  );
}

export class DisasterGlobe {
  constructor(containerEl, options = {}) {
    this.container = containerEl;
    this.options = Object.assign({
      dprCap: 1.0,
      targetFps: 30,
      onSelect: null,
    }, options);

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.worldGroup = null;
    this.earthMesh = null;
    this.starsMesh = null;
    this.markerGroup = null;
    this.exerciseMesh = null;

    this.isPaused = false;
    this.rafId = null;
    this.lastFrameTime = 0;
    this.fpsInterval = 1000 / this.options.targetFps;
    this.isDragging = false;
    this.previousMousePosition = { x: 0, y: 0 };
    this.targetRotation = { x: 0.25, y: -1.2 };
    this.currentRotation = { x: 0.25, y: -1.2 };

    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    this.currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    this.webGlSupported = this._checkWebGL();
  }

  _checkWebGL() {
    try {
      const canvas = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
    } catch (e) {
      return false;
    }
  }

  init() {
    if (!this.webGlSupported) {
      this._render2DFallback("WebGL hardware acceleration not available. Running in 2D Low-Spec Safe Mode.");
      return false;
    }

    const width = this.container.clientWidth || 600;
    const height = this.container.clientHeight || 500;

    // Scene & Camera
    this.scene = new THREE.Scene();
    this._updateBackground();

    this.camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100);
    this.camera.position.z = 3.2;

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'low-power' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.options.dprCap));
    this.renderer.setSize(width, height);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.container.innerHTML = '';
    this.container.appendChild(this.renderer.domElement);

    // World Group
    this.worldGroup = new THREE.Group();
    this.scene.add(this.worldGroup);

    // Stars
    this.starsMesh = makeStars(1000);
    this.scene.add(this.starsMesh);
    if (this.currentTheme === 'light') {
      this.starsMesh.visible = false;
    }

    // Low-geometry sphere (40 x 40 segments for high speed on low-end hardware)
    const geometry = new THREE.SphereGeometry(1, 40, 40);

    const textureLoader = new THREE.TextureLoader();
    const dayMap = textureLoader.load('/static/assets/earth-day.jpg');
    const nightMap = textureLoader.load('/static/assets/earth-night.jpg');
    const specularMap = textureLoader.load('/static/assets/earth-specular.jpg');

    // Shader material for day/night blending and ocean specular reflection
    const surfaceVertex = `
      varying vec2 vUv;
      varying vec3 vNormal;
      varying vec3 vPosition;
      void main() {
        vUv = uv;
        vNormal = normalize(mat3(modelMatrix) * normal);
        vPosition = (modelMatrix * vec4(position, 1.0)).xyz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `;

    const surfaceFragment = `
      uniform sampler2D dayMap;
      uniform sampler2D nightMap;
      uniform sampler2D specularMap;
      uniform vec3 sunDirection;
      varying vec2 vUv;
      varying vec3 vNormal;
      varying vec3 vPosition;
      void main() {
        vec3 normal = normalize(vNormal);
        vec3 sun = normalize(sunDirection);
        float ocean = texture2D(specularMap, vUv).r;
        float illum = dot(normal, sun);
        float dayFactor = smoothstep(-0.1, 0.2, illum);

        vec3 dayColor = texture2D(dayMap, vUv).rgb;
        vec3 nightColor = texture2D(nightMap, vUv).rgb * 1.5;

        vec3 viewDir = normalize(cameraPosition - vPosition);
        float spec = pow(max(0.0, dot(reflect(-sun, normal), viewDir)), 24.0) * ocean * 0.45;

        vec3 color = mix(nightColor, dayColor, dayFactor) + vec3(spec);
        gl_FragColor = vec4(color, 1.0);
      }
    `;

    this.uniforms = {
      dayMap: { value: dayMap },
      nightMap: { value: nightMap },
      specularMap: { value: specularMap },
      sunDirection: { value: new THREE.Vector3(1.5, 0.5, 1.0) },
    };

    const material = new THREE.ShaderMaterial({
      vertexShader: surfaceVertex,
      fragmentShader: surfaceFragment,
      uniforms: this.uniforms,
    });

    this.earthMesh = new THREE.Mesh(geometry, material);
    this.worldGroup.add(this.earthMesh);

    // Hazard Marker Group
    this.markerGroup = new THREE.Group();
    this.earthMesh.add(this.markerGroup);

    // Visakhapatnam Operational Exercise Target Pin
    const vizagCoord = latLonToXYZ(17.6868, 83.2185, 1.018);
    const pinGeom = new THREE.SphereGeometry(0.038, 12, 12);
    const pinMat = new THREE.MeshBasicMaterial({ color: 0xf3c56b }); // Amber
    this.exerciseMesh = new THREE.Mesh(pinGeom, pinMat);
    this.exerciseMesh.position.set(vizagCoord.x, vizagCoord.y, vizagCoord.z);
    this.exerciseMesh.userData = {
      id: "VIZAG-EQ-7.1-EX",
      title: "Visakhapatnam Operational Earthquake Exercise",
      category: "exercise",
      provenance: "SYNTHETIC_EXERCISE",
    };
    this.markerGroup.add(this.exerciseMesh);

    this._bindEvents();
    this._startLoop();
    return true;
  }

  setTheme(theme) {
    this.currentTheme = theme;
    this._updateBackground();
    if (this.starsMesh) {
      this.starsMesh.visible = (theme === 'dark');
    }
  }

  _updateBackground() {
    if (!this.scene) return;
    if (this.currentTheme === 'light') {
      this.scene.background = new THREE.Color(0xf3f5f8);
    } else {
      this.scene.background = new THREE.Color(0x080d12);
    }
  }

  _bindEvents() {
    const dom = this.renderer.domElement;

    dom.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.previousMousePosition = { x: e.clientX, y: e.clientY };
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    dom.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      const deltaX = e.clientX - this.previousMousePosition.x;
      const deltaY = e.clientY - this.previousMousePosition.y;

      this.targetRotation.y += deltaX * 0.005;
      this.targetRotation.x += deltaY * 0.005;
      this.targetRotation.x = Math.max(-1.4, Math.min(1.4, this.targetRotation.x));

      this.previousMousePosition = { x: e.clientX, y: e.clientY };
    });

    dom.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.camera.position.z += e.deltaY * 0.002;
      this.camera.position.z = Math.max(1.8, Math.min(4.5, this.camera.position.z));
    }, { passive: false });

    dom.addEventListener('click', (e) => {
      const rect = dom.getBoundingClientRect();
      this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      this.raycaster.setFromCamera(this.mouse, this.camera);
      const intersects = this.raycaster.intersectObjects(this.markerGroup.children);

      if (intersects.length > 0) {
        const hit = intersects[0].object;
        if (hit.userData && this.options.onSelect) {
          this.options.onSelect(hit.userData);
        }
      }
    });

    window.addEventListener('resize', () => {
      if (!this.renderer || !this.camera) return;
      const w = this.container.clientWidth;
      const h = this.container.clientHeight;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
    });

    document.addEventListener('visibilitychange', () => {
      this.isPaused = document.hidden;
      if (!this.isPaused) {
        this.lastFrameTime = performance.now();
      }
    });
  }

  _startLoop() {
    const loop = (timestamp) => {
      this.rafId = requestAnimationFrame(loop);
      if (this.isPaused) return;

      const elapsed = timestamp - this.lastFrameTime;
      if (elapsed < this.fpsInterval) return;

      this.lastFrameTime = timestamp - (elapsed % this.fpsInterval);

      // Smooth damp rotation
      this.currentRotation.x += (this.targetRotation.x - this.currentRotation.x) * 0.1;
      this.currentRotation.y += (this.targetRotation.y - this.currentRotation.y) * 0.1;

      if (!this.isDragging) {
        this.targetRotation.y += 0.0008; // subtle observatory idle drift
      }

      this.earthMesh.rotation.x = this.currentRotation.x;
      this.earthMesh.rotation.y = this.currentRotation.y;

      // Pulse exercise target pin
      if (this.exerciseMesh) {
        const s = 1.0 + Math.sin(timestamp * 0.004) * 0.2;
        this.exerciseMesh.scale.set(s, s, s);
      }

      this.renderer.render(this.scene, this.camera);
    };
    this.rafId = requestAnimationFrame(loop);
  }

  setEvents(earthquakes = [], wildfires = []) {
    if (!this.markerGroup) return;

    // Remove old hazard markers except exercise pin
    const toRemove = [];
    for (const child of this.markerGroup.children) {
      if (child !== this.exerciseMesh) {
        toRemove.push(child);
      }
    }
    for (const obj of toRemove) {
      this.markerGroup.remove(obj);
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) obj.material.dispose();
    }

    // Quakes: Astra Coral (#ff7765)
    const eqGeom = new THREE.SphereGeometry(0.016, 8, 8);
    const eqMat = new THREE.MeshBasicMaterial({ color: 0xff7765 });

    for (const eq of earthquakes.slice(0, 150)) {
      const p = latLonToXYZ(eq.lat, eq.lon, 1.01);
      const mesh = new THREE.Mesh(eqGeom, eqMat);
      mesh.position.set(p.x, p.y, p.z);
      mesh.userData = { ...eq, sourceCategory: 'EARTHQUAKE' };
      this.markerGroup.add(mesh);
    }

    // Wildfires: Astra Amber (#f3c56b)
    const wfGeom = new THREE.SphereGeometry(0.014, 8, 8);
    const wfMat = new THREE.MeshBasicMaterial({ color: 0xf3c56b });

    for (const wf of wildfires.slice(0, 100)) {
      const p = latLonToXYZ(wf.lat, wf.lon, 1.01);
      const mesh = new THREE.Mesh(wfGeom, wfMat);
      mesh.position.set(p.x, p.y, p.z);
      mesh.userData = { ...wf, sourceCategory: 'WILDFIRE' };
      this.markerGroup.add(mesh);
    }
  }

  focusLocation(lat, lon) {
    const phi = lat * (Math.PI / 180);
    const theta = lon * (Math.PI / 180);
    this.targetRotation.x = phi;
    this.targetRotation.y = -theta - (Math.PI / 2);
  }

  _render2DFallback(message) {
    this.container.innerHTML = `
      <div class="fallback-2d-view" style="padding: 24px; text-align: center; color: var(--ink);">
        <div style="background: var(--amber-wash); border: 1px solid var(--amber); border-radius: 6px; padding: 12px; margin-bottom: 12px;">
          <strong style="color: var(--amber);">2D LOW-SPEC SAFE MODE</strong>
          <p style="font-size: 11px; margin-top: 4px;">${message}</p>
        </div>
      </div>
    `;
  }

  destroy() {
    if (this.rafId) cancelAnimationFrame(this.rafId);
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer.forceContextLoss();
    }
    this.container.innerHTML = '';
  }
}
