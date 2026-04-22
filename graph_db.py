import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

class Neo4jManager:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self):
        self.driver.close()

    def upsert_entities(self, entities: list[dict]):
        with self.driver.session() as session:
            for ent in entities:
                try:
                    if ent['type'] in ('per', 'person'):
                        session.run("MERGE (p:Person {name: $name})", name=ent['text'])
                    elif ent['type'] in ('loc', 'location'):
                        session.run("MERGE (l:Location {name: $name})", name=ent['text'])
                    elif ent['type'] == 'date':
                        session.run("MERGE (d:Date {value: $value})", value=ent['text'])
                except Exception:
                    pass # Fail silently for MVP

    def upsert_relations(self, relations: list[tuple]):
        with self.driver.session() as session:
            for subj, rel_type, obj in relations:
                try:
                    cypher = f"""
                    MATCH (s:Person {{name: $subj}}), (t)
                    WHERE t.name = $obj OR t.value = $obj
                    MERGE (s)-[r:`{rel_type}`]->(t)
                    """
                    session.run(cypher, subj=subj, obj=obj)
                except Exception:
                    pass