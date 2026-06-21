/**
 * attitude.ts
 * -----------
 * Column-major 4x4 matrix helpers for driving the Sketchfab model's orientation
 * from live IMU pitch / roll / yaw. Sketchfab's setMatrix() expects a flat,
 * column-major 16-element matrix in the node's local space (relative to parent),
 * so we compose: final = base * R, which rotates the model about its own origin
 * while preserving the model's authored placement and scale (the `base` matrix).
 */

export type Mat4 = number[]; // length 16, column-major

const deg2rad = (d: number) => (d * Math.PI) / 180;

/** Multiply two column-major matrices: returns a * b. */
export function multiply(a: Mat4, b: Mat4): Mat4 {
  const o = new Array(16);
  for (let c = 0; c < 4; c++) {
    for (let r = 0; r < 4; r++) {
      o[c * 4 + r] =
        a[0 * 4 + r] * b[c * 4 + 0] +
        a[1 * 4 + r] * b[c * 4 + 1] +
        a[2 * 4 + r] * b[c * 4 + 2] +
        a[3 * 4 + r] * b[c * 4 + 3];
    }
  }
  return o;
}

function rotX(rad: number): Mat4 {
  const c = Math.cos(rad), s = Math.sin(rad);
  return [1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1];
}

function rotY(rad: number): Mat4 {
  const c = Math.cos(rad), s = Math.sin(rad);
  return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1];
}

function rotZ(rad: number): Mat4 {
  const c = Math.cos(rad), s = Math.sin(rad);
  return [c, s, 0, 0, -s, c, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
}

/**
 * Which local axis each IMU angle drives. The right mapping depends on how the
 * specific model was authored; these defaults assume a Y-up model facing -Z.
 * Flip a sign here if the truck banks the wrong way for a given model.
 */
export const AXIS = {
  pitch: { fn: rotX, sign: 1 }, // nose up / down
  roll: { fn: rotZ, sign: 1 },  // bank left / right
  yaw: { fn: rotY, sign: 1 },   // heading
};

/**
 * Build the node's local matrix for a given attitude.
 * Rotation order is yaw -> pitch -> roll (heading first, then tilt), applied in
 * the model's local frame, then composed onto the captured base transform.
 */
export function attitudeMatrix(
  base: Mat4,
  pitchDeg: number,
  rollDeg: number,
  yawDeg: number
): Mat4 {
  const r =
    multiply(
      multiply(
        AXIS.yaw.fn(deg2rad(yawDeg * AXIS.yaw.sign)),
        AXIS.pitch.fn(deg2rad(pitchDeg * AXIS.pitch.sign))
      ),
      AXIS.roll.fn(deg2rad(rollDeg * AXIS.roll.sign))
    );
  return multiply(base, r);
}

/** Shortest-path interpolation between two angles in degrees. */
export function lerpAngle(from: number, to: number, t: number): number {
  let delta = ((to - from + 540) % 360) - 180;
  return from + delta * t;
}
