use crate::{GraphError, Topology};
use std::collections::VecDeque;
use std::sync::Arc;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum State {
    Unselected,
    Pending,
    Ready,
    Running,
    Succeeded,
    Reused,
    Failed,
    Blocked,
    Cancelled,
}
impl State {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Unselected => "unselected",
            Self::Pending => "pending",
            Self::Ready => "ready",
            Self::Running => "running",
            Self::Succeeded => "succeeded",
            Self::Reused => "reused",
            Self::Failed => "failed",
            Self::Blocked => "blocked",
            Self::Cancelled => "cancelled",
        }
    }
}

pub struct RunState {
    graph: Arc<Topology>,
    states: Vec<State>,
    remaining: Vec<usize>,
    ready: VecDeque<usize>,
    active: usize,
    capacity: usize,
    unfinished: usize,
}
impl RunState {
    pub fn new(
        graph: Arc<Topology>,
        targets: &[String],
        capacity: usize,
    ) -> Result<Self, GraphError> {
        if capacity == 0 {
            return Err(GraphError("concurrency must be positive".into()));
        }
        let selected = graph.select(targets)?;
        let mut states = vec![State::Unselected; selected.len()];
        let mut ready = VecDeque::new();
        for &i in &graph.order {
            if selected[i] {
                states[i] = if graph.dependencies[i].is_empty() {
                    ready.push_back(i);
                    State::Ready
                } else {
                    State::Pending
                };
            }
        }
        let remaining = graph.dependencies.iter().map(Vec::len).collect();
        let unfinished = selected.iter().filter(|&&s| s).count();
        Ok(Self {
            graph,
            states,
            remaining,
            ready,
            active: 0,
            capacity,
            unfinished,
        })
    }
    pub fn states(&self) -> &[State] {
        &self.states
    }
    pub fn done(&self) -> bool {
        self.unfinished == 0
    }
    pub fn admit(&mut self) -> Vec<usize> {
        let mut admitted = Vec::new();
        while self.active < self.capacity {
            let Some(i) = self.ready.pop_front() else {
                break;
            };
            if self.states[i] != State::Ready {
                continue;
            }
            self.states[i] = State::Running;
            self.active += 1;
            admitted.push(i);
        }
        admitted
    }
    pub fn finish(&mut self, node: usize, outcome: State) -> Result<(), GraphError> {
        if self.states.get(node) != Some(&State::Running) {
            return Err(GraphError(format!("node {node} is not running")));
        }
        if !matches!(
            outcome,
            State::Succeeded | State::Reused | State::Failed | State::Cancelled
        ) {
            return Err(GraphError("invalid completion outcome".into()));
        }
        self.states[node] = outcome;
        self.active -= 1;
        self.unfinished -= 1;
        if matches!(outcome, State::Succeeded | State::Reused) {
            for &next in &self.graph.dependents[node] {
                if self.states[next] == State::Pending {
                    self.remaining[next] -= 1;
                    if self.remaining[next] == 0 {
                        self.states[next] = State::Ready;
                        self.ready.push_back(next);
                    }
                }
            }
        } else {
            let mut queue: VecDeque<_> = self.graph.dependents[node].iter().copied().collect();
            while let Some(next) = queue.pop_front() {
                if matches!(self.states[next], State::Pending | State::Ready) {
                    self.states[next] = State::Blocked;
                    self.unfinished -= 1;
                    queue.extend(&self.graph.dependents[next]);
                }
            }
        }
        Ok(())
    }
    pub fn cancel(&mut self) {
        for state in &mut self.states {
            if matches!(*state, State::Pending | State::Ready) {
                *state = State::Cancelled;
                self.unfinished -= 1;
            }
        }
        self.ready.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Builder;
    fn graph() -> Arc<Topology> {
        let mut b = Builder::new();
        let ids: Vec<_> = ["a", "b", "join", "tail", "other"]
            .iter()
            .map(|s| b.add(s).unwrap())
            .collect();
        for (n, d) in [(2, 0), (2, 1), (3, 2)] {
            b.depends_on(ids[n], ids[d]).unwrap();
        }
        Arc::new(b.compile().unwrap())
    }
    #[test]
    fn joins_both_completion_orders() {
        for order in [[0, 1], [1, 0]] {
            let mut r = RunState::new(graph(), &["tail".into()], 2).unwrap();
            assert_eq!(r.admit(), [0, 1]);
            assert!(r.admit().is_empty());
            r.finish(order[0], State::Succeeded).unwrap();
            assert!(r.admit().is_empty());
            r.finish(order[1], State::Succeeded).unwrap();
            assert_eq!(r.admit(), [2]);
            r.finish(2, State::Succeeded).unwrap();
            assert_eq!(r.admit(), [3]);
            r.finish(3, State::Succeeded).unwrap();
            assert!(r.done());
            assert_eq!(r.states()[4], State::Unselected);
        }
    }
    #[test]
    fn capacity_and_invalid_completion() {
        let mut r = RunState::new(graph(), &["tail".into()], 1).unwrap();
        assert!(r.finish(0, State::Succeeded).is_err());
        assert_eq!(r.admit(), [0]);
        assert!(r.finish(0, State::Ready).is_err());
        assert!(r.finish(99, State::Succeeded).is_err());
        r.finish(0, State::Succeeded).unwrap();
        assert!(r.finish(0, State::Succeeded).is_err());
        assert_eq!(r.admit(), [1]);
        assert!(RunState::new(graph(), &["tail".into()], 0).is_err());
    }
    #[test]
    fn failures_block_only_descendants() {
        let mut r = RunState::new(graph(), &["tail".into(), "other".into()], 3).unwrap();
        assert_eq!(r.admit(), [0, 1, 4]);
        r.finish(0, State::Failed).unwrap();
        assert_eq!(r.states()[2], State::Blocked);
        assert_eq!(r.states()[3], State::Blocked);
        r.finish(1, State::Succeeded).unwrap();
        r.finish(4, State::Succeeded).unwrap();
        assert!(r.done());
        assert!(r.admit().is_empty());
    }
    #[test]
    fn cancel_drains_running_nodes() {
        let mut r = RunState::new(graph(), &["tail".into()], 1).unwrap();
        assert_eq!(r.admit(), [0]);
        r.cancel();
        r.cancel();
        assert!(!r.done());
        assert!(r.admit().is_empty());
        assert_eq!(r.states()[0], State::Running);
        r.finish(0, State::Succeeded).unwrap();
        assert!(r.done());
    }
    #[test]
    fn wide_graph_never_exceeds_capacity() {
        let mut b = Builder::new();
        let targets: Vec<_> = (0..100)
            .map(|i| {
                let n = i.to_string();
                b.add(&n).unwrap();
                n
            })
            .collect();
        let mut r = RunState::new(Arc::new(b.compile().unwrap()), &targets, 7).unwrap();
        let mut seen = std::collections::HashSet::new();
        while !r.done() {
            let batch = r.admit();
            assert!(batch.len() <= 7);
            assert!(!batch.is_empty());
            for n in batch {
                assert!(seen.insert(n));
                r.finish(n, State::Succeeded).unwrap();
            }
        }
        assert_eq!(seen.len(), 100);
    }
}
