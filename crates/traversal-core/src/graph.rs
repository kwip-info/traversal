use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT_GRAPH: AtomicU64 = AtomicU64::new(1);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NodeId {
    owner: u64,
    index: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GraphError(pub String);
impl std::fmt::Display for GraphError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}
impl std::error::Error for GraphError {}

/// Mutable topology builder; handles from another builder are always rejected.
pub struct Builder {
    owner: u64,
    names: Vec<String>,
    by_name: HashMap<String, usize>,
    dependencies: Vec<Vec<usize>>,
    edges: HashSet<(usize, usize)>,
}
impl Default for Builder {
    fn default() -> Self {
        Self::new()
    }
}
impl Builder {
    pub fn new() -> Self {
        Self {
            owner: NEXT_GRAPH.fetch_add(1, Ordering::Relaxed),
            names: vec![],
            by_name: HashMap::new(),
            dependencies: vec![],
            edges: HashSet::new(),
        }
    }
    pub fn add(&mut self, name: &str) -> Result<NodeId, GraphError> {
        if name.trim().is_empty() || self.by_name.contains_key(name) {
            return Err(GraphError(format!(
                "node name must be nonempty and unique: {name:?}"
            )));
        }
        let index = self.names.len();
        self.names.push(name.to_owned());
        self.by_name.insert(name.to_owned(), index);
        self.dependencies.push(vec![]);
        Ok(NodeId {
            owner: self.owner,
            index,
        })
    }
    fn check(&self, node: NodeId) -> Result<usize, GraphError> {
        if node.owner != self.owner || node.index >= self.names.len() {
            Err(GraphError("node belongs to a different graph".into()))
        } else {
            Ok(node.index)
        }
    }
    pub fn depends_on(&mut self, node: NodeId, dependency: NodeId) -> Result<(), GraphError> {
        let node = self.check(node)?;
        let dependency = self.check(dependency)?;
        if node == dependency {
            return Err(GraphError(format!("self dependency: {}", self.names[node])));
        }
        if self.edges.insert((node, dependency)) {
            self.dependencies[node].push(dependency);
        }
        Ok(())
    }
    pub fn compile(&self) -> Result<Topology, GraphError> {
        let mut dependents = vec![vec![]; self.names.len()];
        let mut remaining: Vec<_> = self.dependencies.iter().map(Vec::len).collect();
        for (node, dependencies) in self.dependencies.iter().enumerate() {
            for &dep in dependencies {
                dependents[dep].push(node);
            }
        }
        let mut ready: VecDeque<_> = remaining
            .iter()
            .enumerate()
            .filter_map(|(i, &n)| (n == 0).then_some(i))
            .collect();
        let mut order = Vec::with_capacity(self.names.len());
        while let Some(node) = ready.pop_front() {
            order.push(node);
            for &next in &dependents[node] {
                remaining[next] -= 1;
                if remaining[next] == 0 {
                    ready.push_back(next);
                }
            }
        }
        if order.len() != self.names.len() {
            let blocked: Vec<_> = remaining
                .iter()
                .enumerate()
                .filter_map(|(i, &n)| (n > 0).then_some(self.names[i].as_str()))
                .collect();
            return Err(GraphError(format!(
                "cycle prevents ordering these nodes (including descendants): {}",
                blocked.join(", ")
            )));
        }
        Ok(Topology {
            names: self.names.clone(),
            by_name: self.by_name.clone(),
            dependencies: self.dependencies.clone(),
            dependents,
            order,
        })
    }
}

/// Immutable graph storage. Dense indices are internal to this topology.
#[derive(Debug, Clone)]
pub struct Topology {
    pub(crate) names: Vec<String>,
    by_name: HashMap<String, usize>,
    pub(crate) dependencies: Vec<Vec<usize>>,
    pub(crate) dependents: Vec<Vec<usize>>,
    pub(crate) order: Vec<usize>,
}
impl Topology {
    pub fn names(&self) -> &[String] {
        &self.names
    }
    pub fn dependencies(&self) -> &[Vec<usize>] {
        &self.dependencies
    }
    pub fn dependents(&self) -> &[Vec<usize>] {
        &self.dependents
    }
    pub fn order(&self) -> &[usize] {
        &self.order
    }
    pub fn select(&self, targets: &[String]) -> Result<Vec<bool>, GraphError> {
        if targets.is_empty() {
            return Err(GraphError("at least one target is required".into()));
        }
        let mut selected = vec![false; self.names.len()];
        let mut stack = Vec::new();
        for name in targets {
            stack.push(
                *self
                    .by_name
                    .get(name)
                    .ok_or_else(|| GraphError(format!("unknown target: {name}")))?,
            );
        }
        while let Some(node) = stack.pop() {
            if !selected[node] {
                selected[node] = true;
                stack.extend(&self.dependencies[node]);
            }
        }
        Ok(selected)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn empty_singleton_and_bad_names() {
        let mut b = Builder::new();
        assert!(b.compile().unwrap().names().is_empty());
        assert!(b.add(" ").is_err());
        let a = b.add("a").unwrap();
        assert!(b.add("a").is_err());
        assert!(b.depends_on(a, a).is_err());
        let g = b.compile().unwrap();
        assert_eq!(g.order(), &[0]);
        assert!(g.select(&[]).is_err());
        assert!(g.select(&["missing".into()]).is_err());
    }
    #[test]
    fn foreign_handles_and_frozen_plan() {
        let mut a = Builder::new();
        let mut b = Builder::new();
        let x = a.add("x").unwrap();
        let y = b.add("y").unwrap();
        assert!(a.depends_on(x, y).is_err());
        let frozen = a.compile().unwrap();
        a.add("z").unwrap();
        assert_eq!(frozen.names(), &["x"]);
        assert_eq!(a.compile().unwrap().names().len(), 2);
    }
    #[test]
    fn diamond_closure_and_duplicate_edges() {
        let mut b = Builder::new();
        let ids: Vec<_> = ["a", "b", "c", "d", "unused"]
            .iter()
            .map(|n| b.add(n).unwrap())
            .collect();
        for (n, d) in [(1, 0), (2, 0), (3, 1), (3, 2), (3, 2)] {
            b.depends_on(ids[n], ids[d]).unwrap();
        }
        let g = b.compile().unwrap();
        assert_eq!(g.dependencies()[3], [1, 2]);
        assert_eq!(
            g.select(&["d".into(), "b".into()]).unwrap(),
            [true, true, true, true, false]
        );
    }
    #[test]
    fn cycle_reports_names() {
        let mut b = Builder::new();
        let a = b.add("a").unwrap();
        let c = b.add("c").unwrap();
        b.depends_on(a, c).unwrap();
        b.depends_on(c, a).unwrap();
        let err = b.compile().unwrap_err().to_string();
        assert!(err.contains("a, c"));
    }
    #[test]
    fn long_chain_is_iterative() {
        let mut b = Builder::new();
        let mut prev = None;
        for i in 0..50_000 {
            let id = b.add(&i.to_string()).unwrap();
            if let Some(dep) = prev {
                b.depends_on(id, dep).unwrap();
            }
            prev = Some(id);
        }
        let g = b.compile().unwrap();
        assert_eq!(
            g.select(&["49999".into()])
                .unwrap()
                .iter()
                .filter(|&&s| s)
                .count(),
            50_000
        );
    }
    #[test]
    fn generated_dags_match_transitive_reference() {
        for seed in 0..40usize {
            let mut b = Builder::new();
            let n = 30;
            let ids: Vec<_> = (0..n).map(|i| b.add(&i.to_string()).unwrap()).collect();
            let mut reach = vec![vec![false; n]; n];
            for i in 0..n {
                for j in 0..i {
                    if (i * 17 + j * 31 + seed) % 7 == 0 {
                        b.depends_on(ids[i], ids[j]).unwrap();
                        reach[i][j] = true;
                    }
                }
            }
            for k in 0..n {
                for i in 0..n {
                    for j in 0..n {
                        reach[i][j] |= reach[i][k] && reach[k][j];
                    }
                }
            }
            let g = b.compile().unwrap();
            let mut pos = vec![0; n];
            for (p, &i) in g.order().iter().enumerate() {
                pos[i] = p;
            }
            for i in 0..n {
                let selection = g.select(&[i.to_string()]).unwrap();
                for j in 0..n {
                    assert_eq!(selection[j], i == j || reach[i][j]);
                    if reach[i][j] {
                        assert!(pos[j] < pos[i]);
                    }
                }
            }
        }
    }
}
