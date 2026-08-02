import type { Meta, StoryObj } from "@storybook/react-vite";

import { Card, CardContent, CardHeader, CardTitle } from "./card";

const meta = { title: "UI/Card", component: Card } satisfies Meta<typeof Card>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Event: Story = {
  render: () => (
    <Card className="max-w-sm">
      <CardHeader><CardTitle>Прогулка у моря</CardTitle></CardHeader>
      <CardContent><p>Сегодня, 18:30 · Махачкала</p></CardContent>
    </Card>
  ),
};
