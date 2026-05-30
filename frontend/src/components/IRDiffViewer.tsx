import { useState } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { highlightIR, highlightDiff } from '@/lib/utils'

interface IRDiffViewerProps {
  o0_ir: string
  o2_ir: string
  ir_diff: string
  o3_ir?: string
}

function IRPane({ ir, label }: { ir: string; label: string }) {
  return (
    <div className="h-full overflow-auto bg-[#0d0d1a] rounded-lg border border-border">
      <div className="sticky top-0 z-10 flex items-center gap-2 px-3 py-1.5 bg-[#0d0d1a] border-b border-border">
        <span className="text-[10px] font-mono font-bold text-muted-foreground uppercase">{label}</span>
      </div>
      <pre
        className="text-[11.5px] font-mono leading-[1.7] p-3 overflow-x-auto"
        dangerouslySetInnerHTML={{ __html: highlightIR(ir) || '<span class="text-muted-foreground italic">No IR available</span>' }}
      />
    </div>
  )
}

function DiffPane({ diff }: { diff: string }) {
  return (
    <div className="h-full overflow-auto bg-[#0d0d1a] rounded-lg border border-border">
      <div className="sticky top-0 z-10 flex items-center gap-4 px-3 py-1.5 bg-[#0d0d1a] border-b border-border">
        <span className="text-[10px] font-mono font-bold text-muted-foreground uppercase">Unified Diff: -O0 vs -O2</span>
        <span className="text-[10px] text-green-400">● added at -O2</span>
        <span className="text-[10px] text-red-400">● removed from -O0</span>
      </div>
      <pre
        className="text-[11.5px] font-mono leading-[1.7] p-3 overflow-x-auto"
        dangerouslySetInnerHTML={{ __html: highlightDiff(diff) || '<span class="text-muted-foreground italic">No diff available</span>' }}
      />
    </div>
  )
}

export default function IRDiffViewer({ o0_ir, o2_ir, ir_diff, o3_ir }: IRDiffViewerProps) {
  return (
    <Tabs defaultValue="diff" className="flex flex-col h-full">
      <TabsList className="shrink-0 w-fit">
        <TabsTrigger value="diff">IR Diff</TabsTrigger>
        <TabsTrigger value="o0">IR −O0</TabsTrigger>
        <TabsTrigger value="o2">IR −O2</TabsTrigger>
        {o3_ir && <TabsTrigger value="o3">IR −O3</TabsTrigger>}
      </TabsList>

      <div className="flex-1 overflow-hidden mt-2">
        <TabsContent value="diff" className="h-full m-0">
          <DiffPane diff={ir_diff} />
        </TabsContent>
        <TabsContent value="o0" className="h-full m-0">
          <IRPane ir={o0_ir} label="LLVM IR at -O0 (no optimization)" />
        </TabsContent>
        <TabsContent value="o2" className="h-full m-0">
          <IRPane ir={o2_ir} label="LLVM IR at -O2 (optimizer enabled)" />
        </TabsContent>
        {o3_ir && (
          <TabsContent value="o3" className="h-full m-0">
            <IRPane ir={o3_ir} label="LLVM IR at -O3 (aggressive optimization)" />
          </TabsContent>
        )}
      </div>
    </Tabs>
  )
}
