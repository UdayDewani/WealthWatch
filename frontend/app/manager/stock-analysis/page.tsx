import { Suspense } from 'react';
import { StockAnalysisPanel } from '@/components/wm-analysis/stock-analysis-panel';

export const metadata = {
  title: 'Stock Intelligence | WealthWatch',
  description: 'AI-assisted market condition analysis and authorized client portfolio relevance assessment.',
};

export default function StockAnalysisPage() {
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stock Intelligence & Client Relevance</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Evaluate stock market trends and automatically identify relevant client portfolios requiring manager review.
        </p>
      </div>

      <Suspense
        fallback={
          <div className="space-y-4 animate-pulse">
            <div className="h-12 rounded-xl bg-muted/60" />
            <div className="h-32 rounded-xl bg-muted/60" />
            <div className="h-28 rounded-xl bg-muted/60" />
          </div>
        }
      >
        <StockAnalysisPanel />
      </Suspense>
    </div>
  );
}
