/* eslint-disable */
/**
 * Generated from ../../schemas/*.json by `npm run gen:types`.
 * Do not edit by hand — edit the JSON Schema and run `npm run gen:types` again.
 */

export type Event = SessionStarted | PipelineChanged | TrackUpdated | TrackEnded | SourceHealth | SessionEnded;

/**
 * Always the first line of a log.
 */
export interface SessionStarted {
  app_version: string;
  camera_name: string;
  config: {
    [k: string]: unknown;
  };
  device: "cpu" | "cuda" | "mps";
  event_id: string;
  input_size: number;
  model: string;
  model_sha256: string;
  provenance: Provenance;
  save_stills: boolean;
  schema_version?: string;
  session_id: string;
  source: string;
  source_id: string;
  threat_objects: string[];
  /**
   * ISO-8601 UTC timestamp with milliseconds, e.g. 2026-09-26T18:04:11.231Z.
   */
  ts: string;
  type?: "session.started";
  zone: [number, number][] | null;
  [k: string]: unknown;
}
/**
 * Which scorer, config, model and input size produced the event, plus the hash chain.
 */
export interface Provenance {
  config_sha256: string;
  hash: string;
  input_size: number;
  model_sha256: string;
  prev_hash: string;
  scorer_id: string;
  [k: string]: unknown;
}
export interface PipelineChanged {
  event_id: string;
  input_size: number;
  model: string;
  model_sha256: string;
  provenance: Provenance;
  reason: "fps_below_floor";
  schema_version?: string;
  session_id: string;
  source_id: string;
  /**
   * ISO-8601 UTC timestamp with milliseconds, e.g. 2026-09-26T18:04:11.231Z.
   */
  ts: string;
  type?: "pipeline.changed";
  [k: string]: unknown;
}
export interface TrackUpdated {
  confidence: Confidence;
  event_id: string;
  /**
   * Every threat object currently linked to this person; empty if none.
   */
  links: LinkOut[];
  provenance: Provenance;
  raw: Raw;
  schema_version?: string;
  session_id: string;
  snapshot?: Snapshot | null;
  source_id: string;
  /**
   * One plain-English sentence from a fixed template (like Guardian's hypothesis).
   */
  summary: string;
  threat: Threat;
  track: TrackOut;
  /**
   * ISO-8601 UTC timestamp with milliseconds, e.g. 2026-09-26T18:04:11.231Z.
   */
  ts: string;
  type?: "track.updated";
  unknowns: Unknown[];
  [k: string]: unknown;
}
export interface Confidence {
  dimensions: ConfidenceDimensions;
  /**
   * The mean of the three dimensions, rounded to 2 decimals. Never changes the threat score.
   */
  score: number;
  [k: string]: unknown;
}
export interface ConfidenceDimensions {
  /**
   * The track's likelihood, smoothed over the last 1 s.
   */
  detector: number;
  /**
   * The mean of a brightness term and a sharpness term.
   */
  image_quality: number;
  /**
   * The hit ratio over the last 2 s.
   */
  track_stability: number;
  [k: string]: unknown;
}
export interface LinkOut {
  linked_s: number;
  object_class: string;
  /**
   * The detector's probability for this detection.
   */
  object_likelihood: number;
  object_track_id: number;
  /**
   * Seconds since the object went out of view, while held.
   */
  out_of_view_s?: number | null;
  /**
   * 0-1, describing the link (mean overlap, duration and fade factor).
   */
  strength: number;
  [k: string]: unknown;
}
export interface Raw {
  approach: number;
  /**
   * Continuous seconds inside the zone, tolerating gaps up to 1 s (config), carried across track_restarted.
   */
  dwell_s: number;
  in_zone: boolean;
  truncated: boolean;
  [k: string]: unknown;
}
export interface Snapshot {
  path: string;
  sha256: string;
  [k: string]: unknown;
}
export interface Threat {
  band: "low" | "medium" | "high" | "critical";
  evidence: EvidenceItem[];
  score: number;
  [k: string]: unknown;
}
export interface EvidenceItem {
  /**
   * Integer; all evidence contributions sum exactly to threat.score.
   */
  contribution: number;
  observed: number;
  rule_id: string;
  rule_version: number;
  /**
   * One plain-English sentence from a fixed template.
   */
  text: string;
  threshold: number;
  type: "supporting" | "contradictory";
  [k: string]: unknown;
}
export interface TrackOut {
  /**
   * Normalized [x1, y1, x2, y2].
   *
   * @minItems 4
   * @maxItems 4
   */
  bbox: [number, number, number, number];
  camera_mode: "fixed" | "moving";
  class: string;
  /**
   * The 8-way label for heading_deg.
   */
  direction?: ("up" | "up-right" | "right" | "down-right" | "down" | "down-left" | "left" | "up-left") | null;
  /**
   * Direction on screen, 0° = toward the top of the frame, measured clockwise. Not a compass bearing. Suspended when truncated or the camera is moving.
   */
  heading_deg?: number | null;
  /**
   * The detector's probability for this class.
   */
  likelihood: number;
  /**
   * Distance per second in multiples of the object's own box height.
   */
  speed_body_heights_per_s?: number | null;
  track_id: number;
  [k: string]: unknown;
}
export interface Unknown {
  code: "object_out_of_view" | "track_restarted" | "poor_image" | "camera_moving" | "truncated";
  detail: string;
  [k: string]: unknown;
}
export interface TrackEnded {
  class: string;
  duration_s: number;
  event_id: string;
  peak_band: "low" | "medium" | "high" | "critical";
  peak_score: number;
  provenance: Provenance;
  schema_version?: string;
  session_id: string;
  source_id: string;
  track_id: number;
  /**
   * ISO-8601 UTC timestamp with milliseconds, e.g. 2026-09-26T18:04:11.231Z.
   */
  ts: string;
  type?: "track.ended";
  [k: string]: unknown;
}
export interface SourceHealth {
  code: "fps_low" | "frozen_frame" | "black_frame" | "blur" | "scene_change";
  detail: string;
  event_id: string;
  provenance: Provenance;
  schema_version?: string;
  session_id: string;
  source_id: string;
  /**
   * ISO-8601 UTC timestamp with milliseconds, e.g. 2026-09-26T18:04:11.231Z.
   */
  ts: string;
  type?: "source.health";
  value: number;
  [k: string]: unknown;
}
/**
 * Always the last line of a log that ended normally.
 */
export interface SessionEnded {
  detail?: string | null;
  event_id: string;
  provenance: Provenance;
  reason: "stopped" | "quit" | "error" | "camera_lost" | "idle";
  schema_version?: string;
  session_id: string;
  source_id: string;
  /**
   * ISO-8601 UTC timestamp with milliseconds, e.g. 2026-09-26T18:04:11.231Z.
   */
  ts: string;
  type?: "session.ended";
  [k: string]: unknown;
}

export interface ScoringConfig {
  bands?: BandsConfig;
  confidence?: ConfidenceConfig;
  detect?: DetectConfig;
  eligibility?: EligibilityConfig;
  emit?: EmitConfig;
  health?: HealthConfig;
  link?: LinkConfig;
  motion?: MotionConfig;
  restart?: RestartConfig;
  runtime?: RuntimeConfig;
  tracker?: TrackerConfig;
  weights?: WeightsConfig;
  zone?: ZoneConfig;
}
export interface BandsConfig {
  hysteresis?: number;
}
export interface ConfidenceConfig {
  luma_hi?: number;
  luma_lo?: number;
  sharp_ref?: number;
}
export interface DetectConfig {
  object_min?: number;
  person_min?: number;
  threat_nms_iou?: number;
}
export interface EligibilityConfig {
  object_min_detections?: number;
  person_min_age_s?: number;
  person_min_hit_ratio?: number;
}
export interface EmitConfig {
  heartbeat_s?: number;
}
export interface HealthConfig {
  black_luma?: number;
  blur_var?: number;
  frozen_diff?: number;
  frozen_s?: number;
  scene_change_diff?: number;
}
export interface LinkConfig {
  break_s?: number;
  expand_side?: number;
  expand_top?: number;
  fade_s?: number;
  form_s?: number;
  min_overlap?: number;
  strength_full_s?: number;
}
export interface MotionConfig {
  approach_window_s?: number;
  camera_flow_threshold?: number;
  camera_moving_s?: number;
  smoothing_s?: number;
  truncation_margin?: number;
}
export interface RestartConfig {
  max_distance?: number;
  window_s?: number;
}
export interface RuntimeConfig {
  fps_floor?: number;
  idle_stop_s?: number;
  model?: "auto" | "small" | "large";
  stepdown_after_s?: number;
}
export interface TrackerConfig {
  lost_track_buffer?: number;
  minimum_matching_threshold?: number;
  object_activation?: number;
  person_activation?: number;
}
export interface WeightsConfig {
  approach_max?: number;
  approach_min?: number;
  contradictory?: number;
  in_zone?: number;
  link?: number;
  loiter?: number;
  motion_cap?: number;
  moving_away_shrink?: number;
  run_max?: number;
  run_min?: number;
  unattended?: number;
  unattended_after_s?: number;
}
export interface ZoneConfig {
  dwell_gap_s?: number;
  loiter_s?: number;
}

export interface SessionRequest {
  save_stills?: boolean;
  /**
   * A camera id from GET /cameras.
   */
  source: string;
  /**
   * 1-5 object class words to treat as threats, besides people (people are always tracked).
   */
  threat_objects: string[];
  [k: string]: unknown;
}

export interface ZoneRequest {
  /**
   * Polygon of 3-20 normalized (x, y) points with no self-intersection; null clears the zone.
   */
  zone?: [number, number][] | null;
  [k: string]: unknown;
}
