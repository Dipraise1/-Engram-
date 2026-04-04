import { DocsNav } from "./nav";

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#080608] text-[#c4b5d4]">
      <DocsNav />
      <div className="flex pt-14">
        <div className="hidden lg:block w-60 flex-shrink-0" />
        <main className="flex-1 min-w-0">{children}</main>
      </div>
    </div>
  );
}
