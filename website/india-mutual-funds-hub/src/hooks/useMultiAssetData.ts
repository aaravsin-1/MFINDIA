import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/integrations/supabase/client';
import { AssetReturns } from '@/engine/portfolio';

export interface AssetInfo {
  asset_id: string;
  display_name: string;
  currency: string;
  asset_type: string;
}

export interface MultiAssetData {
  returnsDict: AssetReturns;
  assetInfo: Record<string, AssetInfo>;
  dates: string[];
}

export const useMultiAssetData = () => {
  return useQuery({
    queryKey: ['multiAssetData'],
    queryFn: async (): Promise<MultiAssetData> => {
      // Fetch metadata
      const { data: infoData, error: infoError } = await supabase
        .from('multiasset_info')
        .select('*');
        
      if (infoError) throw infoError;
      
      const assetInfo: Record<string, AssetInfo> = {};
      infoData.forEach(item => {
        assetInfo[item.asset_id] = item;
      });

      // Fetch time series
      const { data: returnData, error: returnError } = await supabase
        .from('multiasset_returns')
        .select('date, asset_id, return, index_value')
        .order('date', { ascending: true });
        
      if (returnError) throw returnError;

      // Extract unique dates in order
      const dateSet = new Set<string>();
      returnData.forEach(row => dateSet.add(row.date));
      const dates = Array.from(dateSet).sort();

      // Pivot into dictionary mapping
      const returnsDict: AssetReturns = {};
      
      // Initialize arrays to 0 for the exact length of dates
      const numMonths = dates.length;
      const dateToIndex = new Map<string, number>();
      dates.forEach((d, i) => dateToIndex.set(d, i));
      
      returnData.forEach(row => {
        if (!returnsDict[row.asset_id]) {
          returnsDict[row.asset_id] = new Array(numMonths).fill(0);
        }
        const idx = dateToIndex.get(row.date);
        if (idx !== undefined) {
          returnsDict[row.asset_id][idx] = row.return;
        }
      });

      return {
        returnsDict,
        assetInfo,
        dates
      };
    },
    // Cache indefinitely to prevent re-fetching on slider drag
    staleTime: Infinity,
    gcTime: Infinity,
  });
};
