import { HeartHandshake } from "lucide-react";

// I-Care brand mark: a caring "heart-handshake" in a soft gradient tile.
export default function BrandMark({
  size = 40,
  large = false,
}: {
  size?: number;
  large?: boolean;
}) {
  return (
    <div
      className={`brand-mark${large ? " lg" : ""}`}
      style={large ? undefined : { width: size, height: size }}
      aria-hidden
    >
      <HeartHandshake size={large ? 34 : Math.round(size * 0.55)} strokeWidth={2} />
    </div>
  );
}
