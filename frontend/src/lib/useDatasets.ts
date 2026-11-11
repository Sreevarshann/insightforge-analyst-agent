"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export const useDatasets = () => useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
