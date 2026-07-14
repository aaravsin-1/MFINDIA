export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      category_summary: {
        Row: {
          avg_quality: number | null
          avg_risk: number | null
          category: string | null
          is_core: boolean | null
          n_funds: number | null
          n_recommended: number | null
          selection_edge_pct: number | null
        }
        Insert: {
          avg_quality?: number | null
          avg_risk?: number | null
          category?: string | null
          is_core?: boolean | null
          n_funds?: number | null
          n_recommended?: number | null
          selection_edge_pct?: number | null
        }
        Update: {
          avg_quality?: number | null
          avg_risk?: number | null
          category?: string | null
          is_core?: boolean | null
          n_funds?: number | null
          n_recommended?: number | null
          selection_edge_pct?: number | null
        }
        Relationships: []
      }
      engine_metrics: {
        Row: {
          group: string | null
          label: string | null
          metric: string | null
          unit: string | null
          value: string | null
        }
        Insert: {
          group?: string | null
          label?: string | null
          metric?: string | null
          unit?: string | null
          value?: string | null
        }
        Update: {
          group?: string | null
          label?: string | null
          metric?: string | null
          unit?: string | null
          value?: string | null
        }
        Relationships: []
      }
      fund_detail: {
        Row: {
          amc: string | null
          aum_as_of: string | null
          aum_cr: number | null
          category: string | null
          fund_name: string | null
          has_holdings: boolean | null
          holding_period: string | null
          holdings_as_of: string | null
          inception_date: string | null
          manager_names: string | null
          nav_points: number | null
          num_holdings: number | null
          num_managers: number | null
          quality: number | null
          recommended: boolean | null
          risk: number | null
          risk_band: string | null
          scheme_id: number | null
          ter_as_of: string | null
          ter_pct: number | null
          top_holding: string | null
        }
        Insert: {
          amc?: string | null
          aum_as_of?: string | null
          aum_cr?: number | null
          category?: string | null
          fund_name?: string | null
          has_holdings?: boolean | null
          holding_period?: string | null
          holdings_as_of?: string | null
          inception_date?: string | null
          manager_names?: string | null
          nav_points?: number | null
          num_holdings?: number | null
          num_managers?: number | null
          quality?: number | null
          recommended?: boolean | null
          risk?: number | null
          risk_band?: string | null
          scheme_id?: number | null
          ter_as_of?: string | null
          ter_pct?: number | null
          top_holding?: string | null
        }
        Update: {
          amc?: string | null
          aum_as_of?: string | null
          aum_cr?: number | null
          category?: string | null
          fund_name?: string | null
          has_holdings?: boolean | null
          holding_period?: string | null
          holdings_as_of?: string | null
          inception_date?: string | null
          manager_names?: string | null
          nav_points?: number | null
          num_holdings?: number | null
          num_managers?: number | null
          quality?: number | null
          recommended?: boolean | null
          risk?: number | null
          risk_band?: string | null
          scheme_id?: number | null
          ter_as_of?: string | null
          ter_pct?: number | null
          top_holding?: string | null
        }
        Relationships: []
      }
      fund_holdings: {
        Row: {
          as_of: string | null
          industry: string | null
          instrument: string | null
          isin: string | null
          pct_nav: number | null
          rank: number | null
          scheme_id: number | null
          source: string | null
        }
        Insert: {
          as_of?: string | null
          industry?: string | null
          instrument?: string | null
          isin?: string | null
          pct_nav?: number | null
          rank?: number | null
          scheme_id?: number | null
          source?: string | null
        }
        Update: {
          as_of?: string | null
          industry?: string | null
          instrument?: string | null
          isin?: string | null
          pct_nav?: number | null
          rank?: number | null
          scheme_id?: number | null
          source?: string | null
        }
        Relationships: []
      }
      fund_managers: {
        Row: {
          is_current: boolean | null
          manager_name: string | null
          scheme_id: number | null
          start_date: string | null
          tenure_years: number | null
        }
        Insert: {
          is_current?: boolean | null
          manager_name?: string | null
          scheme_id?: number | null
          start_date?: string | null
          tenure_years?: number | null
        }
        Update: {
          is_current?: boolean | null
          manager_name?: string | null
          scheme_id?: number | null
          start_date?: string | null
          tenure_years?: number | null
        }
        Relationships: []
      }
      fund_nav: {
        Row: {
          date: string | null
          nav: number | null
          scheme_id: number | null
        }
        Insert: {
          date?: string | null
          nav?: number | null
          scheme_id?: number | null
        }
        Update: {
          date?: string | null
          nav?: number | null
          scheme_id?: number | null
        }
        Relationships: []
      }
      funds: {
        Row: {
          as_of: string | null
          category: string | null
          fund_name: string | null
          holding_period: string | null
          is_core_category: boolean | null
          is_live: boolean | null
          n_negative: number | null
          n_positive: number | null
          quality: number | null
          rank: number | null
          reason_1: string | null
          reason_2: string | null
          recommended: boolean | null
          risk: number | null
          risk_band: string | null
          scheme_id: number | null
          snapshot: string | null
          why: string | null
        }
        Insert: {
          as_of?: string | null
          category?: string | null
          fund_name?: string | null
          holding_period?: string | null
          is_core_category?: boolean | null
          is_live?: boolean | null
          n_negative?: number | null
          n_positive?: number | null
          quality?: number | null
          rank?: number | null
          reason_1?: string | null
          reason_2?: string | null
          recommended?: boolean | null
          risk?: number | null
          risk_band?: string | null
          scheme_id?: number | null
          snapshot?: string | null
          why?: string | null
        }
        Update: {
          as_of?: string | null
          category?: string | null
          fund_name?: string | null
          holding_period?: string | null
          is_core_category?: boolean | null
          is_live?: boolean | null
          n_negative?: number | null
          n_positive?: number | null
          quality?: number | null
          rank?: number | null
          reason_1?: string | null
          reason_2?: string | null
          recommended?: boolean | null
          risk?: number | null
          risk_band?: string | null
          scheme_id?: number | null
          snapshot?: string | null
          why?: string | null
        }
        Relationships: []
      }
      research_log: {
        Row: {
          code: string | null
          finding: string | null
          id: number | null
          reference: string | null
          title: string | null
          verdict: string | null
        }
        Insert: {
          code?: string | null
          finding?: string | null
          id?: number | null
          reference?: string | null
          title?: string | null
          verdict?: string | null
        }
        Update: {
          code?: string | null
          finding?: string | null
          id?: number | null
          reference?: string | null
          title?: string | null
          verdict?: string | null
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
