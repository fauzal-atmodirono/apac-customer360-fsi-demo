"use client";

import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function useApi<T>(path: string) {
  const { data, error, isLoading } = useSWR<T>(`/api/${path}`, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });
  return { data, error, isLoading };
}
