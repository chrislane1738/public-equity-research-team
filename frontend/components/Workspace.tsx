"use client";

import TopBar from "./TopBar";
import Sidebar from "./Sidebar";
import TabBar from "./TabBar";
import ChatPanel from "./ChatPanel";
import FolderTree from "./FolderTree";

export default function Workspace() {
  return (
    <div className="h-screen w-screen flex flex-col">
      <TopBar />
      <div className="flex-1 grid grid-cols-[220px_1fr_320px] overflow-hidden">
        <aside className="border-r border-border overflow-y-auto">
          <Sidebar />
        </aside>
        <main className="flex flex-col overflow-hidden">
          <TabBar />
          <ChatPanel />
        </main>
        <aside className="border-l border-border overflow-y-auto">
          <FolderTree />
        </aside>
      </div>
    </div>
  );
}
