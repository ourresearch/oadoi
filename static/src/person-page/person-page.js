angular.module('personPage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid', {
            templateUrl: 'person-page/person-page.tpl.html',
            controller: 'personPageCtrl',
            resolve: {
                personResp: function($http, $route, Person){
                    console.log("loaded the person response in the route def")
                    return Person.load($route.current.params.orcid)
                },
                badgesResp: function($http, $route, BadgeDefs){
                    console.log("loaded the badge defs in the route def")
                    return BadgeDefs.load()
                }
            }
        })
    })



    .controller("personPageCtrl", function($scope,
                                           $routeParams,
                                           $route,
                                           $http,
                                           Person,
                                           BadgeDefs,
                                           badgesResp,
                                           personResp){
        $scope.person = Person.d
        $scope.badgeDefs = BadgeDefs
        console.log("retrieved the person", $scope.person)

        $scope.profileStatus = "all_good"

        //if (!Person.d.email) {
        //    $scope.userForm = {}
        //    $scope.profileStatus = "no_email"
        //}
        //else if (!Person.d.products) {
        //    $scope.profileStatus = "no_products"
        //}
        //else {
        //    $scope.profileStatus = "all_good"
        //}

        $scope.settingEmail = false
        $scope.submitEmail = function(){
            console.log("setting the email!", $scope.userForm.email)
            $scope.settingEmail = true
            $http.post("/api/me", {email: $scope.userForm.email})
                .success(function(resp){
                    $scope.settingEmail = false
                    $route.reload()
                })
        }




        var badgesWithConfigs = Person.getBadgesWithConfigs(BadgeDefs.d)

        var groupedByLevel = _.groupBy(badgesWithConfigs, "level")

        // ok the badge columns are all set up, put in scope now.
        $scope.badgeCols = [
            {level: "gold", list: groupedByLevel.gold},
            {level: "silver", list: groupedByLevel.silver},
            {level: "bronze", list: groupedByLevel.bronze}
        ]










    })



