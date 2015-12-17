python update.py Package.set_github_contributors --no-rq --id=pypi:scikit-learn
python update.py Package.save_all_people --no-rq --id=pypi:scikit-learn
python update.py Package.dedup_people --no-rq --id=pypi:scikit-learn
python update.py Package.set_credit --no-rq --id=pypi:scikit-learn

echo "**** Now run the sql in set_person_is_organization.sql"