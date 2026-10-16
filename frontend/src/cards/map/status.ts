/** Map layer status shared by the map card shell and the lazily loaded Leaflet chunk (no Leaflet import). */
export type LayerState = "off" | "loading" | "ok" | "unavailable";

export interface MapFrame {
  /** What drives the timeline: radar frames, or Himawari frames while the radar is off. */
  source: "radar" | "satellite";
  time: number;
  index: number;
  count: number;
  playing: boolean;
}

export interface MapStatus {
  radar: LayerState;
  satellite: LayerState;
  cyclones: LayerState;
  /** Cyclones drawn. */
  cycloneCount: number;
  /** Frame on screen; undefined when nothing animates. */
  frame?: MapFrame;
}

export const INITIAL_STATUS: MapStatus = { radar: "off", satellite: "off", cyclones: "off", cycloneCount: 0 };
