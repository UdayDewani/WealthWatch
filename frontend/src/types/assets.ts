export interface AssetItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  prev_close: number | null;
  // commodity extras
  unit?: string;
  icon?: string;
  // forex extras
  base?: string;
  quote?: string;
  // ETF / MF extras
  category?: string;
}

export interface AssetsData {
  commodities: AssetItem[];
  crypto: AssetItem[];
  forex: AssetItem[];
  etfs: AssetItem[];
  mutual_funds: AssetItem[];
  timestamp: string;
}
