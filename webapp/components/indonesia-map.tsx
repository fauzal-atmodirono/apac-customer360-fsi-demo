"use client";

import { Map, Marker } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { money } from "@/lib/format";

const COORDS: Record<string, [number, number]> = {
  JAKARTA: [-6.2088, 106.8456], SURABAYA: [-7.2575, 112.7521], BANDUNG: [-6.9175, 107.6191],
  MEDAN: [3.5952, 98.6722], SEMARANG: [-6.9667, 110.4167], MAKASSAR: [-5.1477, 119.4327],
  DENPASAR: [-8.65, 115.2167], BATAM: [1.0456, 104.0305],
};

type Region = { region: string; customers: number; total_savings: number; avg_ips: number };

export default function IndonesiaMap({ regions }: { regions: Region[] }) {
  const max = Math.max(...regions.map((r) => Number(r.customers)), 1);
  return (
    <div className="h-[420px] w-full overflow-hidden rounded-lg border">
      <Map
        initialViewState={{ latitude: -2.5, longitude: 117, zoom: 3.6 }}
        mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
        attributionControl={false}
      >
        {regions.map((r) => {
          const c = COORDS[r.region];
          if (!c) return null;
          const size = 14 + Math.sqrt(Number(r.customers) / max) * 46;
          return (
            <Marker key={r.region} latitude={c[0]} longitude={c[1]}>
              <div
                title={`${r.region}: ${r.customers} customers · ${money(r.total_savings)} savings`}
                className="flex items-center justify-center rounded-full border-2 border-white text-[10px] font-semibold text-white shadow-md"
                style={{ width: size, height: size, background: "rgba(21,101,192,0.78)" }}
              >
                {r.region.slice(0, 3)}
              </div>
            </Marker>
          );
        })}
      </Map>
    </div>
  );
}
