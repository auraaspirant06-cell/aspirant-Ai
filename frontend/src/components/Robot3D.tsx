"use client";

import React, { useEffect, useRef } from "react";
import * as THREE from "three";

export type RobotState =
  | "IDLE"
  | "LISTENING"
  | "THINKING"
  | "SPEAKING"
  | "CODING"
  | "WORKING"
  | "SUCCESS"
  | "ERROR";

export const ROBOT_STATES: readonly RobotState[] = [
  "IDLE",
  "LISTENING",
  "THINKING",
  "SPEAKING",
  "CODING",
  "WORKING",
  "SUCCESS",
  "ERROR",
] as const;

interface StateStyle {
  accentHex: string;
  glowHex: string;
  badge: string;
}

const STATE_STYLES: Record<RobotState, StateStyle> = {
  IDLE: { accentHex: "#38bdf8", glowHex: "#7c3aed", badge: "Standing By" },
  LISTENING: { accentHex: "#22d3ee", glowHex: "#0ea5e9", badge: "Listening" },
  THINKING: { accentHex: "#a855f7", glowHex: "#6366f1", badge: "Thinking" },
  SPEAKING: { accentHex: "#38bdf8", glowHex: "#a855f7", badge: "Speaking" },
  CODING: { accentHex: "#06b6d4", glowHex: "#3b82f6", badge: "Coding" },
  WORKING: { accentHex: "#818cf8", glowHex: "#22d3ee", badge: "Working" },
  SUCCESS: { accentHex: "#34d399", glowHex: "#10b981", badge: "Success" },
  ERROR: { accentHex: "#f43f5e", glowHex: "#fb7185", badge: "Error" },
};

export interface Robot3DProps {
  state?: RobotState;
  statusText?: string;
  speechAmplitude?: number;
  wakePhrase?: string;
  voiceGender?: "female" | "male";
  onStateSelect?: (state: RobotState) => void;
  compact?: boolean;
}

function canUseWebGL(): boolean {
  try {
    const probe = document.createElement("canvas");
    return Boolean(probe.getContext("webgl2") || probe.getContext("webgl"));
  } catch {
    return false;
  }
}

export function Robot3D({
  state = "IDLE",
  statusText,
  speechAmplitude = 0,
  wakePhrase = "Hey Baby",
  voiceGender = "female",
  onStateSelect,
  compact = false,
}: Robot3DProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const stateRef = useRef<RobotState>(state);
  const ampRef = useRef<number>(speechAmplitude);

  stateRef.current = state;
  ampRef.current = speechAmplitude;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const width = Math.max(240, host.clientWidth || 320);
    const height = compact ? 220 : 280;

    let rafId = 0;
    let renderer: THREE.WebGLRenderer | null = null;
    let resizeObserver: ResizeObserver | null = null;

    const pointer = { x: 0, y: 0 };
    const onPointerMove = (ev: PointerEvent) => {
      const rect = host.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -(((ev.clientY - rect.top) / rect.height) * 2 - 1);
    };
    host.addEventListener("pointermove", onPointerMove);

    if (canUseWebGL()) {
      try {
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
        camera.position.set(0, 0.35, 5.2);

        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setSize(width, height);
        renderer.domElement.className = "h-full w-full block";
        renderer.domElement.setAttribute("aria-label", "Interactive 3D Aspirant AI Robot");
        host.innerHTML = "";
        host.appendChild(renderer.domElement);

        const ambient = new THREE.AmbientLight(0xdbeafe, 1.35);
        scene.add(ambient);
        const keyLight = new THREE.PointLight(0x38bdf8, 28, 20);
        keyLight.position.set(3, 3.5, 4);
        scene.add(keyLight);
        const rimLight = new THREE.PointLight(0x8b5cf6, 22, 20);
        rimLight.position.set(-3.2, -1.5, 3);
        scene.add(rimLight);

        const root = new THREE.Group();
        scene.add(root);

        const shellMat = new THREE.MeshStandardMaterial({
          color: 0x0f172a,
          metalness: 0.72,
          roughness: 0.24,
        });
        const trimMat = new THREE.MeshStandardMaterial({
          color: 0x1e293b,
          metalness: 0.8,
          roughness: 0.2,
        });
        const visorMat = new THREE.MeshStandardMaterial({
          color: 0x050914,
          metalness: 0.9,
          roughness: 0.1,
        });
        const glowMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
        const auraMat = new THREE.MeshBasicMaterial({
          color: 0x7c3aed,
          transparent: true,
          opacity: 0.42,
        });

        // Head group
        const headGroup = new THREE.Group();
        headGroup.position.y = 0.78;
        root.add(headGroup);

        const cranium = new THREE.Mesh(new THREE.SphereGeometry(0.76, 28, 24), shellMat);
        cranium.scale.set(1.06, 0.92, 0.96);
        headGroup.add(cranium);

        const visor = new THREE.Mesh(
          new THREE.BoxGeometry(1.16, 0.62, 0.38),
          visorMat
        );
        visor.position.set(0, -0.02, 0.52);
        headGroup.add(visor);

        // Eyes
        const eyeGeo = new THREE.SphereGeometry(0.11, 16, 16);
        const leftEye = new THREE.Mesh(eyeGeo, glowMat);
        leftEye.position.set(-0.27, 0.05, 0.73);
        const rightEye = new THREE.Mesh(eyeGeo, glowMat);
        rightEye.position.set(0.27, 0.05, 0.73);
        headGroup.add(leftEye, rightEye);

        // Mouth audio equalizer bars (5 segments)
        const mouthBars: THREE.Mesh[] = [];
        for (let i = 0; i < 5; i += 1) {
          const bar = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.05, 0.04), glowMat);
          bar.position.set((i - 2) * 0.13, -0.19, 0.73);
          mouthBars.push(bar);
          headGroup.add(bar);
        }

        // Dual futuristic antenna ear pods
        const podGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.22, 16);
        const leftPod = new THREE.Mesh(podGeo, trimMat);
        leftPod.rotation.z = Math.PI / 2;
        leftPod.position.set(-0.84, 0.04, 0);
        const rightPod = leftPod.clone();
        rightPod.position.set(0.84, 0.04, 0);
        headGroup.add(leftPod, rightPod);

        const antennaStem = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.34, 10), trimMat);
        antennaStem.position.set(0, 0.84, 0);
        const antennaTip = new THREE.Mesh(new THREE.SphereGeometry(0.075, 14, 14), glowMat);
        antennaTip.position.set(0, 1.03, 0);
        headGroup.add(antennaStem, antennaTip);

        // Torso + chest core reactor
        const torsoGroup = new THREE.Group();
        torsoGroup.position.y = -0.58;
        root.add(torsoGroup);

        const torso = new THREE.Mesh(
          new THREE.CylinderGeometry(0.62, 0.44, 1.05, 24),
          shellMat
        );
        torsoGroup.add(torso);

        const chestCore = new THREE.Mesh(new THREE.SphereGeometry(0.19, 20, 20), glowMat);
        chestCore.position.set(0, 0.08, 0.54);
        torsoGroup.add(chestCore);

        const leftArm = new THREE.Mesh(new THREE.CapsuleGeometry(0.11, 0.44, 6, 12), trimMat);
        leftArm.position.set(-0.82, 0.02, 0);
        leftArm.rotation.z = 0.22;
        const rightArm = leftArm.clone();
        rightArm.position.set(0.82, 0.02, 0);
        rightArm.rotation.z = -0.22;
        torsoGroup.add(leftArm, rightArm);

        // Orbital rings & sound wave rings
        const orbitRing = new THREE.Mesh(new THREE.TorusGeometry(1.38, 0.022, 12, 64), glowMat);
        orbitRing.rotation.x = Math.PI / 2.4;
        root.add(orbitRing);

        const waveRing = new THREE.Mesh(new THREE.TorusGeometry(1.65, 0.02, 10, 64), auraMat);
        waveRing.rotation.x = Math.PI / 2;
        waveRing.position.y = -1.2;
        root.add(waveRing);

        const clock = new THREE.Clock();
        const renderLoop = () => {
          rafId = window.requestAnimationFrame(renderLoop);
          const t = clock.getElapsedTime();
          const curState = stateRef.current;
          const style = STATE_STYLES[curState] || STATE_STYLES.IDLE;

          glowMat.color.set(style.accentHex);
          auraMat.color.set(style.glowHex);
          keyLight.color.set(style.accentHex);
          rimLight.color.set(style.glowHex);

          // Floating levitation + breathing
          const bobAmp = curState === "IDLE" ? 0.07 : curState === "ERROR" ? 0.02 : 0.1;
          root.position.y = Math.sin(t * 2.1) * bobAmp;

          // Subtle head tracking + state tilt
          headGroup.rotation.y = THREE.MathUtils.lerp(
            headGroup.rotation.y,
            pointer.x * 0.28 + Math.sin(t * 0.9) * 0.08,
            0.08
          );
          headGroup.rotation.x = THREE.MathUtils.lerp(
            headGroup.rotation.x,
            -pointer.y * 0.18 + (curState === "CODING" ? 0.12 : 0),
            0.08
          );

          // Periodic blinking
          const blinkCycle = t % 3.6;
          const blinkScaleY =
            blinkCycle > 3.38 && curState !== "CODING"
              ? Math.max(0.12, Math.abs(Math.cos((blinkCycle - 3.38) * 14)))
              : 1.0;
          leftEye.scale.set(
            curState === "LISTENING" ? 1.18 : 1.0,
            blinkScaleY * (curState === "SUCCESS" ? 0.65 : 1.0),
            1.0
          );
          rightEye.scale.copy(leftEye.scale);

          // Orbit ring velocity by state
          const ringVel =
            curState === "THINKING" || curState === "WORKING"
              ? 2.2
              : curState === "CODING"
                ? 1.6
                : curState === "LISTENING"
                  ? 1.9
                  : 0.45;
          orbitRing.rotation.z = t * ringVel;
          orbitRing.rotation.y = Math.sin(t * 0.7) * 0.35;

          // Sound-wave halo pulse during listening / speaking
          const waveScale =
            curState === "LISTENING" || curState === "SPEAKING"
              ? 0.92 + Math.abs(Math.sin(t * 5.2)) * 0.36
              : 0.85 + Math.sin(t * 1.4) * 0.04;
          waveRing.scale.set(waveScale, waveScale, 1);

          // Mouth equalizer animation synchronized with TTS amplitude or listening waves
          const liveAmp =
            curState === "SPEAKING"
              ? Math.max(ampRef.current, 0.3 + 0.65 * Math.abs(Math.sin(t * 12)))
              : curState === "LISTENING"
                ? 0.18 + 0.25 * Math.abs(Math.sin(t * 6))
                : 0.08;
          mouthBars.forEach((bar, idx) => {
            const harmonic = 0.65 + 0.35 * Math.sin(t * 11 + idx * 1.3);
            const hScale = curState === "SPEAKING" || curState === "LISTENING" ? 1 + liveAmp * 4.2 * harmonic : 1;
            bar.scale.set(1, hScale, 1);
          });

          // Gentle arm swing
          leftArm.rotation.x = Math.sin(t * 1.8) * (curState === "SPEAKING" ? 0.28 : 0.08);
          rightArm.rotation.x = -Math.sin(t * 1.8) * (curState === "SPEAKING" ? 0.28 : 0.08);

          renderer?.render(scene, camera);
        };
        renderLoop();

        resizeObserver = new ResizeObserver(() => {
          if (!host || !renderer) return;
          const nw = Math.max(240, host.clientWidth || 320);
          const nh = compact ? 220 : 280;
          camera.aspect = nw / nh;
          camera.updateProjectionMatrix();
          renderer.setSize(nw, nh);
        });
        resizeObserver.observe(host);

        return () => {
          window.cancelAnimationFrame(rafId);
          host.removeEventListener("pointermove", onPointerMove);
          resizeObserver?.disconnect();
          renderer?.dispose();
        };
      } catch {
        renderer?.dispose();
        renderer = null;
      }
    }

    // Headless / WebGL-disabled software fallback: real animated geometric 2D projection canvas
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.className = "h-full w-full block";
    canvas.setAttribute("aria-label", "Interactive 3D Aspirant AI Robot Canvas");
    host.innerHTML = "";
    host.appendChild(canvas);

    const ctx = canvas.getContext("2d");
    let phase = 0;
    const drawFallback = () => {
      rafId = window.requestAnimationFrame(drawFallback);
      if (!ctx) return;
      phase += 0.05;
      const curState = stateRef.current;
      const style = STATE_STYLES[curState] || STATE_STYLES.IDLE;
      const cx = canvas.width / 2;
      const cy = canvas.height / 2 - 4 + Math.sin(phase) * 5;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Halo glow
      const grad = ctx.createRadialGradient(cx, cy, 12, cx, cy, 108);
      grad.addColorStop(0, `${style.accentHex}55`);
      grad.addColorStop(0.6, `${style.glowHex}22`);
      grad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, 108, 0, Math.PI * 2);
      ctx.fill();

      // Orbit ring
      ctx.strokeStyle = style.accentHex;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.ellipse(cx, cy + 8, 86, 26, Math.sin(phase * 0.5) * 0.2, 0, Math.PI * 2);
      ctx.stroke();

      // Robot Head
      ctx.fillStyle = "#0f172a";
      ctx.strokeStyle = style.accentHex;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.roundRect(cx - 46, cy - 58, 92, 66, 20);
      ctx.fill();
      ctx.stroke();

      // Visor
      ctx.fillStyle = "#040814";
      ctx.beginPath();
      ctx.roundRect(cx - 34, cy - 42, 68, 38, 10);
      ctx.fill();

      // Blinking eyes
      const blink = phase % 6.2 > 5.8 ? 0.15 : 1;
      ctx.fillStyle = style.accentHex;
      ctx.beginPath();
      ctx.ellipse(cx - 16, cy - 26, 6, 7 * blink, 0, 0, Math.PI * 2);
      ctx.ellipse(cx + 16, cy - 26, 6, 7 * blink, 0, 0, Math.PI * 2);
      ctx.fill();

      // Animated equalizer mouth bars
      for (let i = 0; i < 5; i += 1) {
        const amp =
          curState === "SPEAKING"
            ? 4 + Math.max(ampRef.current * 10, Math.abs(Math.sin(phase * 3 + i)) * 9)
            : curState === "LISTENING"
              ? 3 + Math.abs(Math.sin(phase * 2 + i)) * 5
              : 2.5;
        ctx.fillRect(cx - 18 + i * 8, cy - 11 - amp / 2, 5, amp);
      }

      // Torso + chest core
      ctx.fillStyle = "#111c33";
      ctx.strokeStyle = style.glowHex;
      ctx.beginPath();
      ctx.roundRect(cx - 34, cy + 14, 68, 52, 14);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = style.accentHex;
      ctx.beginPath();
      ctx.arc(cx, cy + 40, 10 + Math.sin(phase * 2) * 2, 0, Math.PI * 2);
      ctx.fill();
    };
    drawFallback();

    return () => {
      window.cancelAnimationFrame(rafId);
      host.removeEventListener("pointermove", onPointerMove);
    };
  }, [compact]);

  const activeStyle = STATE_STYLES[state] || STATE_STYLES.IDLE;

  return (
    <div
      data-testid="robot-3d-panel"
      data-robot-state={state}
      className="glass-panel relative overflow-hidden rounded-2xl p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-widest text-sky-500 dark:text-sky-400">
            Interactive 3D AI Core &bull; Wake: &ldquo;{wakePhrase}&rdquo; ({voiceGender})
          </p>
          <p className="text-xs text-adaptive-muted">
            {statusText || `State: ${state} — ${activeStyle.badge}`}
          </p>
        </div>
        <span
          className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-bold"
          style={{
            borderColor: `${activeStyle.accentHex}66`,
            backgroundColor: `${activeStyle.accentHex}22`,
            color: activeStyle.accentHex,
          }}
        >
          <span
            className="h-2 w-2 rounded-full animate-pulse"
            style={{ backgroundColor: activeStyle.accentHex }}
          />
          {state}
        </span>
      </div>

      <div
        ref={hostRef}
        className={`w-full overflow-hidden rounded-xl border border-sky-500/20 bg-slate-950/75 ${
          compact ? "h-[220px]" : "h-[280px]"
        }`}
      />

      {onStateSelect && (
        <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label="3D Robot State Controls">
          {ROBOT_STATES.map((st) => {
            const active = st === state;
            return (
              <button
                key={st}
                type="button"
                onClick={() => onStateSelect(st)}
                className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
                  active
                    ? "bg-aspirant-gradient text-white shadow-glow"
                    : "surface-card text-adaptive-muted hover:border-sky-500"
                }`}
              >
                {st}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
