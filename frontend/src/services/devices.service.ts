import { api } from "@/utils/api";
import type { Device, DeviceAssignment, DeviceRegister } from "@/types";

export const devicesService = {
  list: () => api.get<{ devices: Device[] }>("/devices").then((r) => r.devices),
  get: (id: string) => api.get<Device>(`/devices/${id}`),
  register: (body: DeviceRegister) => api.post<Device>("/devices", body),
  listAssignments: (id: string) =>
    api
      .get<{ assignments: DeviceAssignment[] }>(`/devices/${id}/assignments`)
      .then((r) => r.assignments),
  addAssignment: (
    id: string,
    body: {
      boat_id: string;
      valid_from?: string;
      valid_to?: string;
      regatta_id?: string;
      race_id?: string;
    },
  ) => api.post<DeviceAssignment>(`/devices/${id}/assignments`, body),
};
