/* eslint-disable */
/**
 * Generated from ../../schemas/*.json by `npm run gen:types`.
 * Do not edit by hand — edit the JSON Schema and run `npm run gen:types` again.
 */

export interface ScoringConfigNumberField {
  section: string
  field: string
  kind: 'number'
  min: number
  max: number
  step: number
  default: number
}
export interface ScoringConfigEnumField {
  section: string
  field: string
  kind: 'enum'
  options: string[]
  default: string
}
export type ScoringConfigField = ScoringConfigNumberField | ScoringConfigEnumField

export const SCORING_CONFIG_FIELDS: ScoringConfigField[] = [
  {
    "section": "bands",
    "field": "hysteresis",
    "kind": "number",
    "min": 0,
    "max": 20,
    "step": 1,
    "default": 5
  },
  {
    "section": "confidence",
    "field": "luma_hi",
    "kind": "number",
    "min": 0,
    "max": 255,
    "step": 1,
    "default": 200
  },
  {
    "section": "confidence",
    "field": "luma_lo",
    "kind": "number",
    "min": 0,
    "max": 255,
    "step": 1,
    "default": 60
  },
  {
    "section": "confidence",
    "field": "sharp_ref",
    "kind": "number",
    "min": 0.1,
    "max": 10000,
    "step": 0.1,
    "default": 100
  },
  {
    "section": "detect",
    "field": "object_min",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.15
  },
  {
    "section": "detect",
    "field": "person_min",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.35
  },
  {
    "section": "detect",
    "field": "threat_nms_iou",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.5
  },
  {
    "section": "eligibility",
    "field": "object_min_detections",
    "kind": "number",
    "min": 1,
    "max": 30,
    "step": 1,
    "default": 3
  },
  {
    "section": "eligibility",
    "field": "person_min_age_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 1
  },
  {
    "section": "eligibility",
    "field": "person_min_hit_ratio",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.6
  },
  {
    "section": "emit",
    "field": "heartbeat_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 2
  },
  {
    "section": "health",
    "field": "black_luma",
    "kind": "number",
    "min": 0,
    "max": 255,
    "step": 1,
    "default": 10
  },
  {
    "section": "health",
    "field": "blur_var",
    "kind": "number",
    "min": 0.1,
    "max": 10000,
    "step": 0.1,
    "default": 20
  },
  {
    "section": "health",
    "field": "frozen_diff",
    "kind": "number",
    "min": 0.1,
    "max": 10000,
    "step": 0.1,
    "default": 1
  },
  {
    "section": "health",
    "field": "frozen_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 2
  },
  {
    "section": "health",
    "field": "scene_change_diff",
    "kind": "number",
    "min": 0.1,
    "max": 10000,
    "step": 0.1,
    "default": 60
  },
  {
    "section": "link",
    "field": "break_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 1
  },
  {
    "section": "link",
    "field": "expand_side",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.15
  },
  {
    "section": "link",
    "field": "expand_top",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.15
  },
  {
    "section": "link",
    "field": "fade_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 3
  },
  {
    "section": "link",
    "field": "form_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 0.5
  },
  {
    "section": "link",
    "field": "min_overlap",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.3
  },
  {
    "section": "link",
    "field": "strength_full_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 2
  },
  {
    "section": "motion",
    "field": "approach_window_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 2
  },
  {
    "section": "motion",
    "field": "camera_flow_threshold",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.01
  },
  {
    "section": "motion",
    "field": "camera_moving_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 1
  },
  {
    "section": "motion",
    "field": "smoothing_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 1
  },
  {
    "section": "motion",
    "field": "truncation_margin",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.01
  },
  {
    "section": "restart",
    "field": "max_distance",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.1
  },
  {
    "section": "restart",
    "field": "window_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 1
  },
  {
    "section": "runtime",
    "field": "fps_floor",
    "kind": "number",
    "min": 1,
    "max": 60,
    "step": 1,
    "default": 10
  },
  {
    "section": "runtime",
    "field": "idle_stop_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 30
  },
  {
    "section": "runtime",
    "field": "model",
    "kind": "enum",
    "options": [
      "auto",
      "small",
      "large"
    ],
    "default": "auto"
  },
  {
    "section": "runtime",
    "field": "stepdown_after_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 5
  },
  {
    "section": "tracker",
    "field": "lost_track_buffer",
    "kind": "number",
    "min": 1,
    "max": 300,
    "step": 1,
    "default": 30
  },
  {
    "section": "tracker",
    "field": "minimum_matching_threshold",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.8
  },
  {
    "section": "tracker",
    "field": "object_activation",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.15
  },
  {
    "section": "tracker",
    "field": "person_activation",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.35
  },
  {
    "section": "weights",
    "field": "approach_max",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.25
  },
  {
    "section": "weights",
    "field": "approach_min",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.05
  },
  {
    "section": "weights",
    "field": "contradictory",
    "kind": "number",
    "min": 0,
    "max": 100,
    "step": 1,
    "default": 5
  },
  {
    "section": "weights",
    "field": "in_zone",
    "kind": "number",
    "min": 0,
    "max": 100,
    "step": 1,
    "default": 25
  },
  {
    "section": "weights",
    "field": "link",
    "kind": "number",
    "min": 0,
    "max": 100,
    "step": 1,
    "default": 55
  },
  {
    "section": "weights",
    "field": "loiter",
    "kind": "number",
    "min": 0,
    "max": 100,
    "step": 1,
    "default": 15
  },
  {
    "section": "weights",
    "field": "motion_cap",
    "kind": "number",
    "min": 0,
    "max": 100,
    "step": 1,
    "default": 20
  },
  {
    "section": "weights",
    "field": "moving_away_shrink",
    "kind": "number",
    "min": 0,
    "max": 1,
    "step": 0.01,
    "default": 0.05
  },
  {
    "section": "weights",
    "field": "run_max",
    "kind": "number",
    "min": 0,
    "max": 10,
    "step": 0.1,
    "default": 2
  },
  {
    "section": "weights",
    "field": "run_min",
    "kind": "number",
    "min": 0,
    "max": 10,
    "step": 0.1,
    "default": 1
  },
  {
    "section": "weights",
    "field": "unattended",
    "kind": "number",
    "min": 0,
    "max": 100,
    "step": 1,
    "default": 30
  },
  {
    "section": "weights",
    "field": "unattended_after_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 2
  },
  {
    "section": "zone",
    "field": "dwell_gap_s",
    "kind": "number",
    "min": 0,
    "max": 60,
    "step": 0.1,
    "default": 1
  },
  {
    "section": "zone",
    "field": "loiter_s",
    "kind": "number",
    "min": 0,
    "max": 120,
    "step": 0.1,
    "default": 10
  }
]
