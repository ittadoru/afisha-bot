import {
  CarFront,
  Dumbbell,
  Gamepad2,
  GraduationCap,
  HandHeart,
  Mountain,
  Palette,
  Shapes,
  Users,
  type LucideIcon,
} from "lucide-react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const CATEGORY_ICONS: Readonly<Record<string, LucideIcon>> = {
  dumbbell: Dumbbell,
  gamepad: Gamepad2,
  users: Users,
  mountain: Mountain,
  "graduation-cap": GraduationCap,
  palette: Palette,
  car: CarFront,
  "hand-heart": HandHeart,
  shapes: Shapes,
};

const LEGACY_SLUG_ICONS: Readonly<Record<string, string>> = {
  sport: "dumbbell",
  games: "gamepad",
  meetups: "users",
  cafe: "users",
  entertainment: "users",
  tourism: "mountain",
  walks: "mountain",
  education: "graduation-cap",
  work: "graduation-cap",
  creativity: "palette",
  cars: "car",
  volunteering: "hand-heart",
  other: "shapes",
};

export function mapCategoryIconMarkup(
  iconKey: string | null,
  categorySlug: string | null,
): string {
  const resolvedKey = iconKey ?? LEGACY_SLUG_ICONS[categorySlug ?? ""] ?? "shapes";
  const Icon = CATEGORY_ICONS[resolvedKey] ?? Shapes;
  return renderToStaticMarkup(
    createElement(Icon, {
      "aria-hidden": true,
      focusable: false,
      strokeWidth: 2.35,
    }),
  );
}
