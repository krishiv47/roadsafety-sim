import React from 'react';
import {
  CircleDot, Construction, Car, Waves, TrafficCone, TreePine,
  OctagonAlert, PawPrint, MapPin, AlertTriangle,
} from 'lucide-react';

/* Event-type → Lucide icon. Replaces backend emoji icons in the UI. */
const TYPE_ICON: Record<string, React.ElementType> = {
  pothole:         CircleDot,
  road_crack:      Construction,
  accident:        Car,
  waterlogging:    Waves,
  heavy_traffic:   TrafficCone,
  fallen_tree:     TreePine,
  roadblock:       OctagonAlert,
  animal_crossing: PawPrint,
};

export function EventIcon({ type, size = 16, color }: { type: string; size?: number; color?: string }) {
  const Icon = TYPE_ICON[type] ?? MapPin;
  return <Icon style={{ width: size, height: size, color }} />;
}

/* Same mapping as inline SVG string — for Leaflet divIcon HTML markers. */
const TYPE_SVG_PATH: Record<string, string> = {
  pothole:         '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="1"/>',
  road_crack:      '<rect x="2" y="6" width="20" height="8" rx="1"/><path d="M17 14v7"/><path d="M7 14v7"/><path d="M17 3v3"/><path d="M7 3v3"/><path d="M10 14 2.3 6.3"/><path d="m14 6 7.7 7.7"/><path d="m8 6 8 8"/>',
  accident:        '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
  waterlogging:    '<path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/>',
  heavy_traffic:   '<path d="M9.3 6.8 12 2l2.7 4.8"/><path d="M6.3 12.3 9 7.5h6l2.7 4.8"/><path d="M3.4 17.7 6.1 13h11.8l2.7 4.7"/><path d="M2 22h20"/>',
  fallen_tree:     '<path d="m17 14 3 3.3a1 1 0 0 1-.7 1.7H4.7a1 1 0 0 1-.7-1.7L7 14h-.3a1 1 0 0 1-.7-1.7L9 9h-.2A1 1 0 0 1 8 7.3L12 3l4 4.3a1 1 0 0 1-.8 1.7H15l3 3.3a1 1 0 0 1-.7 1.7H17Z"/><path d="M12 22v-3"/>',
  roadblock:       '<path d="M12 16h.01"/><path d="M12 8v4"/><path d="M15.3 3.8 20.2 8.7a2 2 0 0 1 .6 1.4v3.8a2 2 0 0 1-.6 1.4l-4.9 4.9a2 2 0 0 1-1.4.6h-3.8a2 2 0 0 1-1.4-.6l-4.9-4.9a2 2 0 0 1-.6-1.4v-3.8a2 2 0 0 1 .6-1.4l4.9-4.9a2 2 0 0 1 1.4-.6h3.8a2 2 0 0 1 1.4.6Z"/>',
  animal_crossing: '<circle cx="11" cy="4" r="2"/><circle cx="18" cy="8" r="2"/><circle cx="20" cy="16" r="2"/><path d="M9 10a5 5 0 0 1 5 5v3.5a3.5 3.5 0 0 1-6.84 1.045Q6.52 17.48 4.46 16.84A3.5 3.5 0 0 1 5.5 10Z"/>',
};

export function eventIconSvg(type: string, size = 14, color = 'currentColor'): string {
  const path = TYPE_SVG_PATH[type] ?? '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
}

export const busIconSvg = (size = 13, color = 'rgba(0,0,0,0.85)') =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 6v6"/><path d="M15 6v6"/><path d="M2 12h19.6"/><path d="M18 18h3s.5-1.7.8-2.8c.1-.4.2-.8.2-1.2 0-.4-.1-.8-.2-1.2l-1.4-5C20.1 6.8 19.1 6 18 6H4a2 2 0 0 0-2 2v10h3"/><circle cx="7" cy="18" r="2"/><path d="M9 18h5"/><circle cx="16" cy="18" r="2"/></svg>`;

export const warnIconSvg = (size = 10, color = '#ef4444') =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="${color}" stroke="${color}" stroke-width="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/></svg>`;

/* Remove emoji/pictographs from backend-generated strings (timeline messages etc.)
   so the UI stays 100% icon-based. */
export function stripEmoji(s: string): string {
  return s
    .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}\u{200D}\u{2190}-\u{21FF}\u{2300}-\u{23FF}]/gu, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}
