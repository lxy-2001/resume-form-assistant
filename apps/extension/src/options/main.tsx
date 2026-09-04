import { createRoot } from "react-dom/client";

import { ProfilePage } from "./ProfilePage";
import { HttpProfileClient } from "./profileClient";

const root = document.getElementById("options-page");
if (root) {
  createRoot(root).render(<ProfilePage client={new HttpProfileClient()} profileId="default-profile" />);
}
