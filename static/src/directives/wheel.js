angular.module("directives.wheel", [])
    .directive("wheel", function(){

        function getWheelVal(credit){
            if (credit <= (1/16)) {
                return "tiny"
            }

            else if (credit >= (15/16) && credit < 1) {
                return "nearly-all"
            }

            else {
                return Math.round(credit * 8)
            }


        }



        return {
            templateUrl: "directives/wheel.tpl.html",
            restrict: "EA",
            link: function(scope, elem, attrs) {

                // we're in a list of authors on the package page
                if (scope.person_package){
                    var personPackage = scope.person_package
                    personPackage.num_authors = scope.package.num_authors
                    personPackage.num_committers = scope.package.num_committers
                    personPackage.num_commits = scope.package.num_commits
                    scope.personName = scope.person_package.name
                }

                // we're in a list of packages on the person page
                else if (scope.package){
                    var personPackage = scope.package
                    scope.personName = scope.person.name

                }


                // handle the popover position
                if (attrs.popoverRight){
                    scope.popoverRight = true
                }
                else {
                    scope.popoverRight = false
                }

                // computet the credit percentage number
                scope.percentCredit = Math.min(
                    100,
                    Math.ceil(personPackage.person_package_credit * 100)
                )

                // figure what wheel image to use
                scope.wheelVal = getWheelVal(personPackage.person_package_credit)
                scope.wheelData = personPackage

                // handy vars for the markup to use
                if (personPackage.roles.github_contributor == personPackage.num_commits) {
                    scope.wheelData.soleCommitter = true
                }



            }
        }


    })















