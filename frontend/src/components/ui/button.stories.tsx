import type { Meta, StoryObj } from "@storybook/react-vite";
import { Bell } from "lucide-react";

import { Button } from "./button";

const meta = { title: "UI/Button", component: Button, tags: ["autodocs"] } satisfies Meta<typeof Button>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = { args: { children: "Ехала →" } };
export const Secondary: Story = { args: { children: "Посмотреть список", variant: "secondary" } };
export const Icon: Story = {
  args: { children: <Bell aria-hidden="true" />, variant: "outline", size: "icon", "aria-label": "Уведомления" },
};
