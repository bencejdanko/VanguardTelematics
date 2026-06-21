import { useEffect, useRef, useState } from 'react';
import styles from './CybertruckViewer.module.css';
import { Cube, Warning } from '@phosphor-icons/react';
import { Mat4, attitudeMatrix, lerpAngle } from '../lib/attitude';

// The model the user provided: "2027 Taffy Bayou" (Cybertruck) on Sketchfab.
const MODEL_UID = '175690ab8cf44b30b5552e640d30f38e';
const SKETCHFAB_API = 'https://static.sketchfab.com/api/sketchfab-viewer-1.12.1.js';

declare global {
  interface Window {
    Sketchfab?: any;
  }
}

function loadSketchfabApi(): Promise<any> {
  return new Promise((resolve, reject) => {
    if (window.Sketchfab) return resolve(window.Sketchfab);
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SKETCHFAB_API}"]`);
    if (existing) {
      existing.addEventListener('load', () => resolve(window.Sketchfab));
      existing.addEventListener('error', reject);
      return;
    }
    const s = document.createElement('script');
    s.src = SKETCHFAB_API;
    s.async = true;
    s.onload = () => resolve(window.Sketchfab);
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

interface Props {
  pitch: number;
  roll: number;
  yaw: number;
  isEmergency: boolean;
}

interface Euler {
  pitch: number;
  roll: number;
  yaw: number;
}

export const CybertruckViewer = ({ pitch, roll, yaw, isEmergency }: Props) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const apiRef = useRef<any>(null);
  const nodeRef = useRef<number | null>(null);
  const baseRef = useRef<Mat4 | null>(null);
  const targetRef = useRef<Euler>({ pitch: 0, roll: 0, yaw: 0 });
  const currentRef = useRef<Euler>({ pitch: 0, roll: 0, yaw: 0 });
  const lastPushedRef = useRef<Euler>({ pitch: 999, roll: 999, yaw: 999 });
  const rafRef = useRef<number | null>(null);

  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  // Keep the live attitude target in a ref so the animation loop reads the
  // latest values without re-subscribing every frame.
  useEffect(() => {
    targetRef.current = { pitch, roll, yaw };
  }, [pitch, roll, yaw]);

  useEffect(() => {
    let cancelled = false;
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    loadSketchfabApi()
      .then((Sketchfab) => {
        if (cancelled || !iframeRef.current) return;
        const client = new Sketchfab(iframeRef.current);
        client.init(MODEL_UID, {
          autostart: 1,
          preload: 1,
          transparent: 1,
          autospin: 1,
          ui_infos: 0,
          ui_controls: 0,
          ui_stop: 0,
          ui_watermark: 0,
          ui_watermark_link: 0,
          ui_ar: 0,
          ui_help: 0,
          ui_settings: 0,
          ui_vr: 0,
          ui_fullscreen: 0,
          ui_annotations: 0,
          scrollwheel: 0,
          ui_theme: 'dark',
          success: (api: any) => {
            apiRef.current = api;
            api.start();
            api.addEventListener('viewerready', () => {
              if (cancelled) return;
              // Find the model's root transform node so we can drive its orientation.
              api.getNodeMap((err: any, nodes: Record<string, any>) => {
                if (err || cancelled) return;
                const transform = Object.values(nodes).find(
                  (n: any) => n.type === 'MatrixTransform'
                ) as any;
                if (!transform) return;
                nodeRef.current = transform.instanceID;
                api.getMatrix(transform.instanceID, (mErr: any, matrix: Mat4) => {
                  if (mErr || cancelled) return;
                  baseRef.current = matrix;
                  setReady(true);
                  startLoop();
                });
              });
            });
          },
          error: () => {
            if (!cancelled) setFailed(true);
          },
        });
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    const startLoop = () => {
      const tick = () => {
        const api = apiRef.current;
        const base = baseRef.current;
        const node = nodeRef.current;
        if (api && base && node != null) {
          const cur = currentRef.current;
          const tgt = targetRef.current;
          const t = prefersReduced ? 1 : 0.12;
          cur.pitch = lerpAngle(cur.pitch, tgt.pitch, t);
          cur.roll = lerpAngle(cur.roll, tgt.roll, t);
          cur.yaw = lerpAngle(cur.yaw, tgt.yaw, t);

          const last = lastPushedRef.current;
          const moved =
            Math.abs(cur.pitch - last.pitch) > 0.05 ||
            Math.abs(cur.roll - last.roll) > 0.05 ||
            Math.abs(cur.yaw - last.yaw) > 0.05;
          if (moved) {
            api.setMatrix(node, attitudeMatrix(base, cur.pitch, cur.roll, cur.yaw));
            last.pitch = cur.pitch;
            last.roll = cur.roll;
            last.yaw = cur.yaw;
          }
        }
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    };

    return () => {
      cancelled = true;
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      apiRef.current = null;
    };
  }, []);

  return (
    <div className={`${styles.viewer} ${isEmergency ? styles.emergency : ''}`}>
      <div className={styles.topBar}>
        <span className={styles.badge}>
          <Cube size={15} weight="duotone" /> Attitude Model
        </span>
        <span className={`${styles.liveDot} ${ready ? styles.liveOn : ''}`}>
          {ready ? 'Tracking' : 'Linking'}
        </span>
      </div>

      <iframe
        ref={iframeRef}
        className={styles.frame}
        title="Cybertruck attitude model"
        allow="autoplay; fullscreen; xr-spatial-tracking"
      />

      {!ready && !failed && (
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <span>Spinning up 3D telemetry...</span>
        </div>
      )}

      {failed && (
        <div className={styles.loading}>
          <Warning size={28} weight="duotone" />
          <span>3D model unavailable. Telemetry still live below.</span>
        </div>
      )}

      <div className={styles.hud}>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>Pitch</span>
          <span className={`${styles.hudValue} mono`}>{pitch.toFixed(1)}°</span>
        </div>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>Roll</span>
          <span className={`${styles.hudValue} mono`}>{roll.toFixed(1)}°</span>
        </div>
        <div className={styles.hudChip}>
          <span className={styles.hudLabel}>Yaw</span>
          <span className={`${styles.hudValue} mono`}>{yaw.toFixed(1)}°</span>
        </div>
      </div>
    </div>
  );
};
