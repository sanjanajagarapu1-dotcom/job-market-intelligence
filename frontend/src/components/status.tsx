import { Skeleton } from "@/components/ui/skeleton";

/** Shown while waiting for the API. The free Render server sleeps when idle. */
export function Loading({ slow, height = "h-64" }: { slow?: boolean; height?: string }) {
  return (
    <div className="space-y-2">
      <Skeleton className={`w-full ${height}`} />
      {slow && (
        <p className="text-sm text-muted-foreground">
          Waking up the free server. The first request can take up to a minute…
        </p>
      )}
    </div>
  );
}

export function ErrorMessage({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
      Something went wrong: {message}
    </p>
  );
}
