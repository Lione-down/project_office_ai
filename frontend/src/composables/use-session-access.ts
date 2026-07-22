import { storeToRefs } from "pinia";

import { useSessionStore } from "@/store/session";

export function useSessionAccess() {
  return storeToRefs(useSessionStore());
}
