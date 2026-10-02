import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProgramStep } from "@/components/ProgramStep";

const { programs, roadmaps } = vi.hoisted(() => ({ programs: vi.fn(), roadmaps: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), api: { programs, roadmaps } }));

const cs = { id: 605, title: "Bachelor of Science in Computer Science", slug: "cs", college: "Science & Engineering", department: null, degree_type: "B.S.", level: "undergraduate", concentration: null };
const art = { ...cs, id: 7, title: "Bachelor of Arts in Art", slug: "art", college: "Creative Arts", degree_type: "B.A." };

beforeEach(() => {
  programs.mockReset();
  roadmaps.mockReset();
  programs.mockResolvedValue({ programs: [cs, art] });
});

test("lists programs and searches as the student types", async () => {
  render(<ProgramStep onChosen={() => {}} />);
  expect(await screen.findByText(cs.title)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Search programs"), "art");
  await waitFor(() => expect(programs).toHaveBeenLastCalledWith("art", ""));
});

test("filters by level", async () => {
  render(<ProgramStep onChosen={() => {}} />);
  await screen.findByText(cs.title);
  await userEvent.click(screen.getByRole("button", { name: "Graduate" }));
  await waitFor(() => expect(programs).toHaveBeenLastCalledWith("", "graduate"));
});

test("picking a program with several roadmaps preselects the default and continues with it", async () => {
  roadmaps.mockResolvedValue({
    roadmaps: [
      { id: 1, name: `${cs.title} Roadmap - Quantitative Reasoning Category 1/2`, is_default: false, total_units_required: 120, major_units: 74 },
      { id: 2, name: `${cs.title} Roadmap Quantitative Reasoning Category 3/4`, is_default: true, total_units_required: 120, major_units: 74 },
    ],
  });
  const onChosen = vi.fn();
  render(<ProgramStep onChosen={onChosen} />);
  await userEvent.click(await screen.findByText(cs.title));
  expect(await screen.findByRole("radio", { name: /Category 3\/4/ })).toBeChecked();
  await userEvent.click(screen.getByRole("radio", { name: /Category 1\/2/ }));
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(onChosen).toHaveBeenCalledWith({ id: 605, title: cs.title, roadmapId: 1 });
});

test("a program with no roadmap cannot be continued", async () => {
  roadmaps.mockResolvedValue({ roadmaps: [] });
  render(<ProgramStep onChosen={() => {}} />);
  await userEvent.click(await screen.findByText(art.title));
  expect(await screen.findByText(/doesn.t have a published roadmap/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
});

test("a failed search shows a message instead of an empty list", async () => {
  programs.mockRejectedValue(new Error("boom"));
  render(<ProgramStep onChosen={() => {}} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(/couldn.t load programs/i);
});

test("picking a degree clears the list so only that choice and its roadmap options remain, and Change brings the list back", async () => {
  roadmaps.mockResolvedValue({ roadmaps: [{ id: 1, name: `${cs.title} Roadmap`, is_default: true, total_units_required: 120, major_units: 74 }] });
  render(<ProgramStep onChosen={() => {}} />);
  await userEvent.click(await screen.findByText(art.title));
  expect(screen.queryByText(cs.title)).not.toBeInTheDocument(); // the other degrees are gone
  expect(screen.queryByLabelText("Search programs")).not.toBeInTheDocument();
  expect(screen.getByText(art.title)).toBeInTheDocument(); // the chosen one stays
  await userEvent.click(screen.getByRole("button", { name: "Change program" }));
  expect(await screen.findByText(cs.title)).toBeInTheDocument();
  expect(screen.getByLabelText("Search programs")).toBeInTheDocument();
});

test("opens with the confirmed degree already chosen: no list, just its roadmap options", async () => {
  roadmaps.mockResolvedValue({
    roadmaps: [
      { id: 1, name: `${cs.title} Roadmap - Quantitative Reasoning Category 1/2`, is_default: false, total_units_required: 120, major_units: 74 },
      { id: 2, name: `${cs.title} Roadmap Quantitative Reasoning Category 3/4`, is_default: true, total_units_required: 120, major_units: 74 },
    ],
  });
  const onChosen = vi.fn();
  render(<ProgramStep initial={cs} onChosen={onChosen} />);
  expect(screen.getByText(cs.title)).toBeInTheDocument();
  expect(screen.queryByLabelText("Search programs")).not.toBeInTheDocument();
  expect(await screen.findByRole("radio", { name: /Category 3\/4/ })).toBeChecked();
  expect(roadmaps).toHaveBeenCalledWith(cs.id);
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(onChosen).toHaveBeenCalledWith({ id: 605, title: cs.title, roadmapId: 2 });
});

test("a confirmed degree can still be changed", async () => {
  roadmaps.mockResolvedValue({ roadmaps: [] });
  render(<ProgramStep initial={cs} onChosen={() => {}} />);
  await userEvent.click(screen.getByRole("button", { name: "Change program" }));
  expect(await screen.findByLabelText("Search programs")).toBeInTheDocument();
});
