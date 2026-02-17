import { Assistant } from "@/app/assistant";

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <Assistant />
      {children}
    </>
  );
}
