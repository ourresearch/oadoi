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
                                           $mdDialog,
                                           $location,
                                           Person,
                                           BadgeDefs,
                                           badgesResp,
                                           personResp){




        $scope.person = Person.d
        $scope.badgeDefs = BadgeDefs
        $scope.products = Person.d.products
        $scope.sources = Person.d.sources



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


        // belt stuff
        $scope.beltInfo = Person.getBeltInfo()
        console.log("beltinfo", $scope.beltInfo)





        // badge stuff
        var badgesWithConfigs = Person.getBadgesWithConfigs(BadgeDefs.d)
        $scope.badges = badgesWithConfigs



        var groupedByLevel = _.groupBy(badgesWithConfigs, "level")

        // ok the badge columns are all set up, put in scope now.
        $scope.badgeCols = [
            {level: "gold", list: groupedByLevel.gold},
            {level: "silver", list: groupedByLevel.silver},
            {level: "bronze", list: groupedByLevel.bronze}
        ]

        $scope.badgeLimit = 3

        $scope.numBadgesToShow = 3
        $scope.toggleBadges = function(){
            if ($scope.numBadgesToShow == 3) {
                $scope.numBadgesToShow = 9999999999
            }
            else {
                $scope.numBadgesToShow = 3
            }
        }


        // posts stuff
        $scope.posts = []
        _.each(Person.d.products, function(product){
            var myDoi = product.doi
            var myTitle = product.title
            _.each(product.posts, function(myPost){
                myPost.citesDoi = myDoi
                myPost.citesTitle = myTitle
                $scope.posts.push(myPost)
            })
        })

        // tweeters are like posts.
        var uniqueTweeters = {}
        _.each(Person.d.products, function(product){
            _.each(product.tweeters, function(tweeter){
                uniqueTweeters[tweeter.url] = tweeter
            })
        })
        $scope.tweeters = _.values(uniqueTweeters)


        // workspace
        $scope.workspace = "achievements"
        $scope.viewThisSource = null
        $scope.setWorkspace = function(workspaceName, viewThisSource){
            console.log("setWorkspace", workspaceName, viewThisSource)

            if (viewThisSource == "twitter"){
                $scope.workspace = "twitter"
                console.log("setting workspace to twitter!")
                return true
            }


            $scope.workspace = workspaceName
            $scope.viewThisSource = viewThisSource
        }




        // dialog stuff
        $scope.personScoreModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title('The online impact score')
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                //.targetEvent(ev)
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("learn more")
                $location.path("about/metrics")
            }, function() {
                console.log("ok")
            });
        };

        $scope.beltModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var title =  $scope.beltInfo.descr  + " online impact (" + Person.d.belt + " belt!)"
            var title = "Online Impact score"
            var confirm = $mdDialog.confirm()
                .title(title)
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("ok")
            }, function() {
                $location.path("about/metrics")
            });
        };

        $scope.tIndexModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title("t-index")
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("ok")
            }, function() {
                $location.path("about/metrics")
            });
        };


        $scope.impressionsModal = function(ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.confirm()
                .title("Twitter impressions")
                .textContent("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque vitae sem nec lectus tincidunt lacinia vitae id sem. Donec sit amet felis eget lorem viverra luctus vel vel libero. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc semper turpis a nulla pharetra hendrerit. Nulla suscipit vulputate eros vel efficitur. Donec a mauris sollicitudin, malesuada nunc ac, pulvinar libero. ")
                .ok('ok')
                .cancel('learn more');

            $mdDialog.show(confirm).then(function() {
                console.log("ok")
            }, function() {
                $location.path("about/metrics")
            });
        };






    })



