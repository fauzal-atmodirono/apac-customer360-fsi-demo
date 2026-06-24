"use client";

import { Map, Marker } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { money } from "@/lib/format";

const COORDS: Record<string, [number, number]> = {
  "KUALA LUMPUR": [3.139, 101.6869], "JOHOR BAHRU": [1.4927, 103.7414],
  "GEORGE TOWN": [5.4141, 100.3288], "IPOH": [4.5975, 101.0901],
  "SHAH ALAM": [3.0733, 101.5185], "KOTA KINABALU": [5.9804, 116.0735],
  "KUCHING": [1.5535, 110.3593], "MALACCA": [2.1896, 102.2501],
};

type Region = { region: string; customers: number; total_savings: number; avg_ips: number };

export default function MalaysiaMap({ regions }: { regions: Region[] }) {
  const max = Math.max(...regions.map((r) => Number(r.customers)), 1);
  return (
    <div className="h-[420px] w-full overflow-hidden rounded-lg border">
      <Map
        initialViewState={{ latitude: 3.8, longitude: 108, zoom: 3.9 }}
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
