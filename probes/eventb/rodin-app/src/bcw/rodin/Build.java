package bcw.rodin;

import java.io.File;
import java.io.IOException;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.Map;
import java.util.concurrent.CompletionService;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorCompletionService;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import org.eclipse.core.resources.IMarker;
import org.eclipse.core.resources.IProject;
import org.eclipse.core.resources.IProjectDescription;
import org.eclipse.core.resources.IResource;
import org.eclipse.core.resources.IWorkspace;
import org.eclipse.core.resources.IncrementalProjectBuilder;
import org.eclipse.core.resources.ResourcesPlugin;
import org.eclipse.core.runtime.NullProgressMonitor;
import org.eclipse.core.runtime.jobs.Job;
import org.eclipse.equinox.app.IApplication;
import org.eclipse.equinox.app.IApplicationContext;
import org.eventb.core.EventBPlugin;
import org.eventb.core.IPSRoot;
import org.eventb.core.IPSStatus;
import org.eventb.core.pm.IProofAttempt;
import org.eventb.core.pm.IProofComponent;
import org.eventb.core.ast.BinaryExpression;
import org.eventb.core.ast.Formula;
import org.eventb.core.ast.FreeIdentifier;
import org.eventb.core.ast.IntegerLiteral;
import org.eventb.core.ast.Predicate;
import org.eventb.core.ast.RelationalPredicate;
import org.eventb.core.seqprover.IAutoTacticRegistry;
import org.eventb.core.seqprover.IParameterSetting;
import org.eventb.core.seqprover.IParameterizerDescriptor;
import org.eventb.core.seqprover.IProofMonitor;
import org.eventb.core.seqprover.IProofTree;
import org.eventb.core.seqprover.IProofTreeNode;
import org.eventb.core.seqprover.IProverSequent;
import org.eventb.core.seqprover.ProverFactory;
import org.eventb.core.seqprover.eventbExtensions.Tactics;
import org.eventb.smt.core.IConfigDescriptor;
import org.eventb.smt.core.ISolverDescriptor;
import org.eventb.smt.core.SMTCore;
import org.eventb.smt.core.SolverKind;
import org.eventb.core.seqprover.proofBuilder.ProofBuilder;
import org.eventb.core.seqprover.ITactic;
import org.eventb.core.seqprover.SequentProver;
import org.rodinp.core.IRodinProject;
import org.rodinp.core.RodinCore;

/**
 * Imports each project directory named on the command line, builds it in full, and proves each
 * obligation: Rodin's default tactics, then the first solver (z3new by default) alone for a short time on the selected hypotheses.
 * A goal still open then gets two searches at once. One runs every SMT solver at once on the goal
 * alone, then on the selected hypotheses, then on all of them, each attempt within the timeout. The
 * other, for a goal over a variable that a hypothesis bounds to at most bcw.split values (default 8),
 * splits the goal into one case for each value. The first search to prove the goal wins.
 * The obligations of a file are proved bcw.jobs (default 4) at once.
 *
 * Properties: bcw.timeout (ms, default 6000), bcw.first (ms that the first solver has alone first, default 700), bcw.solvers (order, default z3new,z3a2,cvc5,veriT),
 * bcw.report (CSV of obligation, result, ms, prover), bcw.baseline (an earlier report to compare),
 * bcw.measure (try every solver on every open goal, and report each attempt), bcw.cvc5 and bcw.z3new (the paths
 * of a cvc5 and a newer Z3 binary, else the cvc5 and z3 on PATH, which become the solvers cvc5, z3new
 * and z3a2, the newer Z3 with its older arithmetic solver).
 */
public class Build implements IApplication {
    private static final NullProgressMonitor NONE = new NullProgressMonitor();

    private long timeout;
    private ITactic quick, quickAll;
    private static final int SPLIT = Integer.getInteger("bcw.split", 8);
    private static final int JOBS = Integer.getInteger("bcw.jobs", 4);
    private List<String> solvers;
    private boolean measure;
    private ITactic rodin;
    private final Map<String, ITactic> smt = new HashMap<>();
    private final List<String> report = new ArrayList<>();
    private final List<String> attempts = new ArrayList<>();

    public Object start(IApplicationContext context) throws Exception {
        timeout = Long.getLong("bcw.timeout", 6000);
        String cvc5 = System.getProperty("bcw.cvc5", onPath("cvc5")), z3new = System.getProperty("bcw.z3new", onPath("z3"));
        System.out.println("SOLVERS z3new=" + z3new + " cvc5=" + cvc5);
        if (cvc5 != null) addSolver("cvc5", SolverKind.CVC4, cvc5, System.getProperty("bcw.cvc5args", "--finite-model-find"));
        if (z3new != null) {
            addSolver("z3new", SolverKind.Z3, z3new, System.getProperty("bcw.z3newargs", ""));
            // The arithmetic solvers of Z3 4.16 prove different goals, so the older one is a second solver.
            addSolver("z3a2", SolverKind.Z3, z3new, "smt.arith.solver=2");
        }
        solvers = List.of(System.getProperty("bcw.solvers", "z3new,z3a2,cvc5,veriT").split(","));
        Set<String> known = new HashSet<>();
        for (IConfigDescriptor config : SMTCore.getConfigurations()) known.add(config.getName());
        for (String solver : solvers)
            if (!known.contains(solver)) {
                System.out.println("ERROR the solver " + solver + " is not available: name its binary with bcw.z3new or bcw.cvc5, or put z3 and cvc5 on PATH");
                return Integer.valueOf(2);
            }
        measure = System.getProperty("bcw.measure") != null;
        rodin = EventBPlugin.getAutoPostTacticManager().getAutoTacticPreference().getDefaultDescriptor().getTacticInstance();
        IAutoTacticRegistry registry = SequentProver.getAutoTacticRegistry();
        IParameterizerDescriptor parameterizer = registry.getParameterizerDescriptor("org.eventb.smt.core.SMTParam");
        for (String solver : solvers)
            for (boolean restricted : new boolean[] {true, false}) {
                IParameterSetting setting = parameterizer.makeParameterSetting();
                setting.setString("configName", solver);
                setting.setBoolean("restricted", restricted);
                setting.setLong("timeOutDelay", timeout);
                smt.put(key(solver, restricted), parameterizer.instantiate(setting, "bcw." + key(solver, restricted)).getTacticInstance());
            }
        IParameterSetting first = parameterizer.makeParameterSetting();
        first.setString("configName", solvers.get(0));
        first.setBoolean("restricted", true);
        first.setLong("timeOutDelay", Long.getLong("bcw.first", 700));
        quick = parameterizer.instantiate(first, "bcw.quick").getTacticInstance();
        first.setBoolean("restricted", false);
        quickAll = parameterizer.instantiate(first, "bcw.quickAll").getTacticInstance();
        String[] arguments = (String[]) context.getArguments().get(IApplicationContext.APPLICATION_ARGS);
        IWorkspace workspace = ResourcesPlugin.getWorkspace();
        int errors = 0;
        for (String directory : arguments) {
            org.eclipse.core.runtime.Path location = new org.eclipse.core.runtime.Path(new File(directory).getAbsolutePath());
            IProjectDescription description = workspace.loadProjectDescription(location.append(".project"));
            description.setLocation(location);
            IProject project = workspace.getRoot().getProject(description.getName());
            if (!project.exists()) project.create(description, null);
            if (!project.isOpen()) project.open(null);
            project.refreshLocal(IResource.DEPTH_INFINITE, null);
            project.build(IncrementalProjectBuilder.FULL_BUILD, null);
            Job.getJobManager().join(ResourcesPlugin.FAMILY_MANUAL_BUILD, null);
            errors += prove(RodinCore.valueOf(project));
        }
        for (IMarker marker : workspace.getRoot().findMarkers(IMarker.PROBLEM, true, IResource.DEPTH_INFINITE)) {
            if (marker.getAttribute(IMarker.SEVERITY, IMarker.SEVERITY_INFO) != IMarker.SEVERITY_ERROR) continue;
            errors++;
            System.out.println("ERROR " + marker.getResource().getFullPath() + ": " + marker.getAttribute(IMarker.MESSAGE, ""));
        }
        write("bcw.report", report);
        if (measure) write("bcw.measure", attempts);
        compare();
        workspace.save(true, null);
        return errors == 0 ? IApplication.EXIT_OK : Integer.valueOf(1);
    }

    /**
     * Registers the binary at path as the solver and configuration name, of the plug-in's kind. The
     * plug-in has no kind for cvc5, so cvc5 runs as a CVC4, by default with the one option of the CVC4
     * configuration that cvc5 keeps; bcw.cvc5args replaces the options. bcw.z3new names a newer Z3, and bcw.z3newargs
     * gives its options.
     */
    /** The absolute path of the program name in a directory of PATH, or null. */
    private static String onPath(String name) {
        for (String directory : System.getenv().getOrDefault("PATH", "").split(File.pathSeparator)) {
            File file = new File(directory, name);
            if (file.canExecute()) return file.getAbsolutePath();
        }
        return null;
    }

    private static void addSolver(String name, SolverKind kind, String path, String args) {
        List<ISolverDescriptor> solvers = new ArrayList<>(Arrays.asList(SMTCore.getSolvers()));
        solvers.add(SMTCore.newSolverDescriptor(name, kind, new org.eclipse.core.runtime.Path(path)));
        SMTCore.setSolvers(solvers.toArray(new ISolverDescriptor[0]));
        List<IConfigDescriptor> configs = new ArrayList<>(Arrays.asList(SMTCore.getConfigurations()));
        configs.add(SMTCore.newConfigDescriptor(name, name, args, true));
        SMTCore.setConfigurations(configs.toArray(new IConfigDescriptor[0]));
    }

    private static String key(String solver, boolean restricted) {
        return solver + (restricted ? "/selected" : "/all");
    }

    /** Proves each obligation of the project, bcw.jobs at once, and returns the number left open. */
    private int prove(IRodinProject project) throws Exception {
        int open = 0;
        for (IPSRoot root : project.getRootElementsOfType(IPSRoot.ELEMENT_TYPE)) {
            IProofComponent component = EventBPlugin.getProofManager().getProofComponent(root);
            IPSStatus[] statuses = root.getStatuses();
            String[] lines = new String[statuses.length];
            ExecutorService pool = Executors.newFixedThreadPool(measure ? 1 : JOBS);
            List<Future<Boolean>> closed = new ArrayList<>();
            for (int i = 0; i < statuses.length; i++) {
                int k = i;
                closed.add(pool.submit(() -> prove(project, root, component, statuses[k], lines, k)));
            }
            try {
                for (Future<Boolean> one : closed) if (!one.get()) open++;
            } catch (ExecutionException e) {
                throw new IllegalStateException(e.getCause());
            } finally {
                pool.shutdown();
            }
            report.addAll(Arrays.asList(lines));
            component.save(NONE, true);
        }
        return open;
    }

    /** Proves one obligation and writes its report line; returns whether it is closed. */
    private boolean prove(IRodinProject project, IPSRoot root, IProofComponent component, IPSStatus status,
                          String[] lines, int k) throws Exception {
        String name = project.getElementName() + "/" + root.getElementName() + "/" + status.getElementName();
        long begin = System.nanoTime();
        IProofAttempt attempt;
        synchronized (component) {
            attempt = component.createProofAttempt(status.getElementName(), "bcw", NONE);
        }
        IProofTreeNode top = attempt.getProofTree().getRoot();
        rodin.apply(top, null);
        // The provers that closed the goals, each with the number of goals that it closed.
        Map<String, Integer> closers = new LinkedHashMap<>();
        if (top.isClosed()) closers.put("rodin", 1);
        for (IProofTreeNode node : top.getOpenDescendants()) {
            String closer = smt(name, node);
            if (closer == null) break;
            closers.merge(closer, 1, Integer::sum);
        }
        StringBuilder prover = new StringBuilder();
        closers.forEach((p, n) -> prover.append(prover.length() > 0 ? " " : "").append(n > 1 ? p + "×" + n : p));
        boolean closed = attempt.getProofTree().isClosed();
        synchronized (component) {
            if (closed) attempt.commit(true, NONE);
            attempt.dispose();
        }
        long ms = (System.nanoTime() - begin) / 1000000;
        lines[k] = name + "," + (closed ? "proved" : "open") + "," + ms + "," + (closed ? prover : "");
        System.out.printf("%s %s %d ms %s%n", closed ? "PROVED" : "OPEN  ", name, ms, closed ? prover : "");
        return closed;
    }

    /** Closes the goal by the first solver to prove it; returns that solver, or null. */
    private String smt(String name, IProofTreeNode node) throws InterruptedException {
        if (!measure) {
            if (quick.apply(node, null) == null) return solvers.get(0) + "/quick";
            return contest(node);
        }
        String closer = null;
        for (boolean restricted : new boolean[] {true, false})
            for (String solver : solvers) {
                if (closer != null && !measure) return closer;
                long begin = System.nanoTime();
                Object failure = smt.get(key(solver, restricted)).apply(node, null);
                long ms = (System.nanoTime() - begin) / 1000000;
                if (measure) {
                    attempts.add(name + "," + key(solver, restricted) + "," + (failure == null ? "proved" : "failed") + "," + ms);
                    if (failure == null) {
                        if (closer == null) closer = key(solver, restricted);
                        node.pruneChildren();   // So that the next solver is measured on the same goal.
                    }
                } else if (failure == null) closer = key(solver, restricted);
            }
        if (measure && closer != null) smt.get(closer).apply(node, null);
        return closer;
    }

    /** The hypotheses that a set of solvers sees. */
    private enum Hyps { NONE, SELECTED, ALL }

    /** A closed copy of a goal, and what closed it. */
    private record Proof(IProofTree tree, String closer) {}

    /**
     * Two searches at once, each on its own copy of the goal: the sets of solvers, and a split into
     * cases. The first to close its copy wins, its proof is grafted onto the goal, and the other stops.
     */
    private String contest(IProofTreeNode node) throws InterruptedException {
        IProverSequent sequent = node.getSequent();
        Range range = smallRange(sequent);
        Stop stop = new Stop(null);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        CompletionService<Proof> done = new ExecutorCompletionService<>(pool);
        done.submit(() -> sets(sequent, stop));
        if (range != null) done.submit(() -> split(sequent, range, stop));
        try {
            for (int i = 0; i < (range == null ? 1 : 2); i++) {
                Proof proof = done.take().get();
                if (proof == null) continue;
                if (ProofBuilder.reuse(node, proof.tree().getRoot(), null) && node.isClosed()) return proof.closer();
                node.pruneChildren();
            }
            return null;
        } catch (ExecutionException e) {
            throw new IllegalStateException(e.getCause());
        } finally {
            stop.setCanceled(true);
            pool.shutdown();
            pool.awaitTermination(1, TimeUnit.MINUTES);
        }
    }

    /** Every solver at once on the goal alone, then on the selected hypotheses, then on all of them. */
    private Proof sets(IProverSequent sequent, Stop stop) throws InterruptedException {
        for (Hyps hyps : Hyps.values()) {
            if (stop.isCanceled()) return null;
            Proof proof = race(sequent, hyps, stop);
            if (proof != null) return proof;
        }
        return null;
    }

    /** Every solver at once, each on its own copy of the goal; the first proof wins and the rest stop. */
    private Proof race(IProverSequent sequent, Hyps hyps, Stop outer) throws InterruptedException {
        // A proof of the goal alone holds under any hypotheses, so it grafts onto the full goal.
        IProverSequent goal = hyps == Hyps.NONE
            ? ProverFactory.makeSequent(sequent.typeEnvironment(), List.<Predicate>of(), sequent.goal()) : sequent;
        Stop stop = new Stop(outer);
        ExecutorService pool = Executors.newFixedThreadPool(solvers.size());
        CompletionService<Proof> done = new ExecutorCompletionService<>(pool);
        for (String solver : solvers) {
            ITactic tactic = smt.get(key(solver, hyps != Hyps.ALL));
            String closer = solver + "/" + hyps.name().toLowerCase();
            done.submit(() -> {
                IProofTree copy = ProverFactory.makeProofTree(goal, null);
                tactic.apply(copy.getRoot(), stop);
                return copy.isClosed() ? new Proof(copy, closer) : null;
            });
        }
        try {
            for (int i = 0; i < solvers.size(); i++) {
                Proof proof = done.take().get();
                if (proof != null) return proof;
            }
            return null;
        } catch (ExecutionException e) {
            throw new IllegalStateException(e.getCause());
        } finally {
            stop.setCanceled(true);
            pool.shutdown();
            pool.awaitTermination(1, TimeUnit.MINUTES);
        }
    }

    /** A variable of the goal that a hypothesis bounds to a few values. */
    private record Range(String variable, int low, int high) {}

    private static Range smallRange(IProverSequent sequent) {
        Set<String> inGoal = new HashSet<>();
        for (FreeIdentifier identifier : sequent.goal().getFreeIdentifiers()) inGoal.add(identifier.getName());
        for (Predicate hypothesis : sequent.visibleHypIterable()) {
            if (hypothesis.getTag() != Formula.IN) continue;
            RelationalPredicate in = (RelationalPredicate) hypothesis;
            if (in.getLeft().getTag() != Formula.FREE_IDENT || in.getRight().getTag() != Formula.UPTO) continue;
            BinaryExpression range = (BinaryExpression) in.getRight();
            if (range.getLeft().getTag() != Formula.INTLIT || range.getRight().getTag() != Formula.INTLIT) continue;
            String variable = ((FreeIdentifier) in.getLeft()).getName();
            BigInteger low = ((IntegerLiteral) range.getLeft()).getValue();
            BigInteger high = ((IntegerLiteral) range.getRight()).getValue();
            // A register's range, such as 0 ‥ 4294967295, is far too wide to split, and too wide for an int.
            if (inGoal.contains(variable) && high.subtract(low).compareTo(BigInteger.valueOf(SPLIT)) < 0)
                return new Range(variable, low.intValueExact(), high.intValueExact());
        }
        return null;
    }

    /**
     * Rodin's case rule on a copy of the goal, one case for each value of the variable. Each case gets
     * Rodin's tactics, then short attempts by Z3, and only then the sets of solvers.
     */
    private Proof split(IProverSequent sequent, Range range, Stop stop) throws InterruptedException {
        IProofTree copy = ProverFactory.makeProofTree(sequent, null);
        IProofTreeNode rest = copy.getRoot();
        for (int value = range.low(); value <= range.high(); value++) {
            if (Tactics.doCase(range.variable() + " = " + value).apply(rest, null) != null) return null;
            IProofTreeNode[] children = rest.getChildNodes();
            rest = children[children.length - 1];   // The case in which the variable is not this value.
        }
        for (IProofTreeNode leaf : copy.getRoot().getOpenDescendants()) {
            rodin.apply(leaf, null);
            for (IProofTreeNode goal : leaf.getOpenDescendants()) {
                if (stop.isCanceled()) return null;
                if (quick.apply(goal, stop) == null || quickAll.apply(goal, stop) == null) continue;
                Proof proof = sets(goal.getSequent(), stop);
                if (proof == null || !ProofBuilder.reuse(goal, proof.tree().getRoot(), null) || !goal.isClosed()) return null;
            }
        }
        return new Proof(copy, "split(" + range.variable() + ")");
    }

    /** Tells the solvers that are still running to stop. */
    private static final class Stop implements IProofMonitor {
        private final Stop parent;
        private volatile boolean canceled;
        Stop(Stop parent) { this.parent = parent; }
        public boolean isCanceled() { return canceled || parent != null && parent.isCanceled(); }
        public void setCanceled(boolean value) { canceled = value; }
        public void setTask(String name) {}
    }

    private static void write(String property, List<String> lines) throws IOException {
        String path = System.getProperty(property);
        if (path != null && !path.equals("1")) Files.write(Path.of(path), lines);
    }

    /** Prints each obligation that the baseline proved and this run did not, or that became much slower (over 1 s and over 1.5 times the baseline). */
    private void compare() throws IOException {
        String path = System.getProperty("bcw.baseline");
        if (path == null) return;
        Map<String, String[]> before = new LinkedHashMap<>();
        for (String line : Files.readAllLines(Path.of(path))) before.put(line.split(",")[0], line.split(",", -1));
        for (String line : report) {
            String[] now = line.split(",", -1), was = before.get(now[0]);
            if (was == null) continue;
            long msNow = Long.parseLong(now[2]), msWas = Long.parseLong(was[2]);
            if (was[1].equals("proved") && now[1].equals("open"))
                System.out.println("LOST   " + now[0] + " (proved by " + was[3] + " in " + msWas + " ms)");
            else if (now[1].equals("proved") && msNow > 1000 && 2 * msNow > 3 * msWas)
                System.out.println("SLOWER " + now[0] + " " + msWas + " ms → " + msNow + " ms");
        }
    }

    public void stop() {
    }
}
