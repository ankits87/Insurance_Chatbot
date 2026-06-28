export interface Source {
  source_file: string;
  product_name: string;
  section: string;
  subsection: string;
  topic: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  grounded: boolean;
  products: string[];
}

export interface HistoryTurn {
  query: string;
  answer: string;
  sources: Source[];
  grounded: boolean;
  products: string[];
  created_at: string;
}

export interface Message {
  role: "user" | "assistant";
  text: string;
  sources?: Source[];
  products?: string[];
}
