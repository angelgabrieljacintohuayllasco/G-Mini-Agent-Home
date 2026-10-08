// Generado por tools/codegen/gen_expressions.py desde common/expressions.json. No editar a mano.
"use strict";
window.GMINI_PRESETS = Object.freeze({
  "reference": {
    "width": 128,
    "height": 64
  },
  "colors": {
    "background": "#000000",
    "eye": "#3FE0FF",
    "glow": "#0B4A5C",
    "accent": "#FF4D6D",
    "text": "#E6FBFF"
  },
  "timing": {
    "shape_tau_ms": 70,
    "gaze_tau_ms": 45,
    "level_attack_ms": 25,
    "level_release_ms": 140,
    "blink_close_ms": 70,
    "blink_hold_ms": 35,
    "blink_open_ms": 110,
    "sleep_after_ms": 600000,
    "shake_ms": 900
  },
  "emotions": {
    "neutral": {
      "w": 36.0,
      "h": 36.0,
      "r": 8.0,
      "gap": 10.0,
      "dy": 0.0,
      "lid_top": 0.0,
      "slant_in": 0.0,
      "slant_out": 0.0,
      "lid_bottom": 0.0,
      "look_x": 0.0,
      "look_y": 0.0,
      "scale_l": 1.0,
      "scale_r": 1.0,
      "bounce": 0.0,
      "shake": 0.0,
      "pulse": 0.0,
      "pulse_hz": 1.2,
      "blink": [
        2200,
        6000
      ],
      "saccade": [
        900,
        3200
      ],
      "shape": "round",
      "accent": false
    },
    "happy": {
      "w": 36.0,
      "h": 38.0,
      "r": 8.0,
      "gap": 10.0,
      "dy": -1.0,
      "lid_top": 0.0,
      "slant_in": 0.0,
      "slant_out": 0.0,
      "lid_bottom": 0.46,
      "look_x": 0.0,
      "look_y": 0.0,
      "scale_l": 1.0,
      "scale_r": 1.0,
      "bounce": 0.8,
      "shake": 0.0,
      "pulse": 0.0,
      "pulse_hz": 1.2,
      "blink": [
        2200,
        6000
      ],
      "saccade": [
        1400,
        3600
      ],
      "shape": "round",
      "accent": false
    },
    "sad": {
      "w": 36.0,
      "h": 30.0,
      "r": 8.0,
      "gap": 10.0,
      "dy": 5.0,
      "lid_top": 0.0,
      "slant_in": 0.0,
      "slant_out": 0.5,
      "lid_bottom": 0.0,
      "look_x": 0.0,
      "look_y": 0.35,
      "scale_l": 1.0,
      "scale_r": 1.0,
      "bounce": 0.0,
      "shake": 0.0,
      "pulse": 0.0,
      "pulse_hz": 1.2,
      "blink": [
        3000,
        7000
      ],
      "saccade": [
        2600,
        6000
      ],
      "shape": "round",
      "accent": false
    },
    "surprised": {
      "w": 40.0,
      "h": 44.0,
      "r": 16.0,
      "gap": 8.0,
      "dy": -2.0,
      "lid_top": 0.0,
      "slant_in": 0.0,
      "slant_out": 0.0,
      "lid_bottom": 0.0,
      "look_x": 0.0,
      "look_y": 0.0,
      "scale_l": 1.0,
      "scale_r": 1.0,
      "bounce": 0.0,
      "shake": 0.0,
      "pulse": 0.0,
      "pulse_hz": 1.2,
      "blink": [
        3500,
        8000
      ],
      "saccade": [
        1600,
        4000
      ],
      "shape": "round",
      "accent": false
    },
    "angry": {
      "w": 36.0,
      "h": 31.0,
      "r": 8.0,
      "gap": 10.0,
      "dy": 2.0,
      "lid_top": 0.04,
      "slant_in": 0.55,
      "slant_out": 0.0,
      "lid_bottom": 0.0,
      "look_x": 0.0,
      "look_y": 0.0,
      "scale_l": 1.0,
      "scale_r": 1.0,
      "bounce": 0.0,
      "shake": 0.0,
      "pulse": 0.0,
      "pulse_hz": 1.2,
      "blink": [
        2200,
        6000
      ],
      "saccade": [
        1200,
        3000
      ],
      "shape": "round",
      "accent": false
    },
    "thinking": {
      "w": 36.0,
      "h": 36.0,
      "r": 8.0,
      "gap": 10.0,
      "dy": 0.0,
      "lid_top": 0.12,
      "slant_in": 0.0,
      "slant_out": 0.0,
      "lid_bottom": 0.0,
      "look_x": 0.55,
      "look_y": -0.45,
      "scale_l": 1.0,
      "scale_r": 0.84,
      "bounce": 0.0,
      "shake": 0.0,
      "pulse": 0.0,
      "pulse_hz": 1.2,
      "blink": [
        2200,
        6000
      ],
      "saccade": [
        1800,
        4200
      ],
      "shape": "round",
      "accent": false
    },
    "sleepy": {
      "w": 36.0,
      "h": 36.0,
      "r": 8.0,
      "gap": 10.0,
      "dy": 3.0,
      "lid_top": 0.55,
      "slant_in": 0.0,
      "slant_out": 0.12,
      "lid_bottom": 0.0,
      "look_x": 0.0,
      "look_y": 0.0,
      "scale_l": 1.0,
      "scale_r": 1.0,
      "bounce": 0.0,
      "shake": 0.0,
      "pulse": 0.0,
      "pulse_hz": 1.2,
      "blink": [
        1500,
        3600
      ],
      "saccade": [
        4000,
        9000
      ],
      "shape": "round",
      "accent": false
    },
    "love": {
      "w": 36.0,
      "h": 34.0,
      "r": 8.0,
      "gap": 10.0,
      "dy": 0.0,
      "lid_top": 0.0,
      "slant_in": 0.0,
      "slant_out": 0.0,
      "lid_bottom": 0.0,
      "look_x": 0.0,
      "look_y": 0.0,
      "scale_l": 1.0,
      "scale_r": 1.0,
      "bounce": 0.0,
      "shake": 0.0,
      "pulse": 0.09,
      "pulse_hz": 1.3,
      "blink": [
        2200,
        6000
      ],
      "saccade": [
        2000,
        5000
      ],
      "shape": "heart",
      "accent": true
    },
    "error": {
      "w": 30.0,
      "h": 30.0,
      "r": 8.0,
      "gap": 10.0,
      "dy": 0.0,
      "lid_top": 0.0,
      "slant_in": 0.0,
      "slant_out": 0.0,
      "lid_bottom": 0.0,
      "look_x": 0.0,
      "look_y": 0.0,
      "scale_l": 1.0,
      "scale_r": 1.0,
      "bounce": 0.0,
      "shake": 2.2,
      "pulse": 0.0,
      "pulse_hz": 1.2,
      "blink": [
        0,
        0
      ],
      "saccade": [
        0,
        0
      ],
      "shape": "cross",
      "accent": true
    }
  },
  "activities": {
    "idle": {
      "mul_w": 1.0,
      "mul_h": 1.0,
      "add_dy": 0.0,
      "lid_top_min": 0.0,
      "level_h": 0.0,
      "look": null,
      "scan": null,
      "saccade": null,
      "blink": null,
      "mouth": false
    },
    "listening": {
      "mul_w": 1.05,
      "mul_h": 1.1,
      "add_dy": 0.0,
      "lid_top_min": 0.0,
      "level_h": 0.12,
      "look": [
        0.0,
        0.0
      ],
      "scan": null,
      "saccade": [
        0,
        0
      ],
      "blink": [
        4000,
        9000
      ],
      "mouth": false
    },
    "thinking": {
      "mul_w": 1.0,
      "mul_h": 1.0,
      "add_dy": 0.0,
      "lid_top_min": 0.14,
      "level_h": 0.0,
      "look": null,
      "scan": {
        "x": 0.5,
        "y": -0.45,
        "ms": [
          1100,
          1900
        ]
      },
      "saccade": null,
      "blink": [
        2600,
        6000
      ],
      "mouth": false
    },
    "acting": {
      "mul_w": 1.0,
      "mul_h": 1.0,
      "add_dy": 0.0,
      "lid_top_min": 0.22,
      "level_h": 0.0,
      "look": null,
      "scan": {
        "x": 0.65,
        "y": 0.1,
        "ms": [
          320,
          650
        ]
      },
      "saccade": null,
      "blink": [
        2000,
        5000
      ],
      "mouth": false
    },
    "speaking": {
      "mul_w": 1.0,
      "mul_h": 1.0,
      "add_dy": -6.0,
      "lid_top_min": 0.0,
      "level_h": -0.14,
      "look": null,
      "scan": null,
      "saccade": [
        1500,
        3500
      ],
      "blink": null,
      "mouth": true
    }
  },
  "aliases": {
    "calm": "neutral",
    "curious": "surprised",
    "tired": "sleepy",
    "confused": "thinking",
    "sorry": "sad",
    "joy": "happy",
    "excited": "happy",
    "fear": "surprised"
  }
});
